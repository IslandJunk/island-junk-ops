"""QuickBooks customer import (CLAUDE.md §13).

Parse an uploaded **QuickBooks Customer Contact List** export (CSV), classify each
row as a commercial company or a residential person, dedupe against what's already in
the DB (and within the batch) on **phone/email** so re-imports never duplicate, and
upsert into `company_customer` / `residential_customer`.

The importer is header-tolerant: QuickBooks Online and Desktop label columns
differently, and reports carry a title/preamble above the real header row. We find the
header row by matching known aliases, then map columns by alias. If a real export uses
a heading we don't recognise, add it to `COLUMN_ALIASES` — no other code changes.

Property-management firms (the 3-level `pm_*` tree) are NOT derivable from a flat
contact list, so they stay app-entered; this importer only fills residential + company.
Charging/invoicing is untouched (guardrail §2).
"""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path

from sqlalchemy import or_, select
from sqlalchemy.orm import Session as DbSession

from app.models.customer import CompanyCustomer, ResidentialCustomer
from app.models.enums import Brand, CustomerSource

# field -> accepted header names (compared case/space/punctuation-insensitively).
COLUMN_ALIASES: dict[str, list[str]] = {
    "customer": ["customer", "customer full name", "display name", "name"],
    "full_name": ["full name"],   # QB's person-name column (separate from the display "Customer")
    "first": ["first name", "first", "given name"],
    "last": ["last name", "last", "surname", "family name"],
    "company": ["company", "company name", "organization", "organisation"],
    "phone": ["phone", "phone numbers", "main phone", "phone number", "telephone",
              "mobile", "mobile phone", "work phone", "cell"],
    "email": ["email", "email address", "main email", "e-mail", "e mail"],
    "address": ["full address", "billing address", "bill to", "address", "street",
                "billing street", "shipping address"],
    "city": ["billing city", "city"],
    "province": ["billing province", "billing state", "province", "state"],
    "postal": ["billing postal code", "billing zip", "postal code", "zip"],
}


def _key(s: str) -> str:
    """Normalise a header/name cell for matching: lowercase, strip non-alphanumerics."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


# reverse lookup: normalised header -> field
_HEADER_TO_FIELD: dict[str, str] = {}
for _field, _names in COLUMN_ALIASES.items():
    for _n in _names:
        _HEADER_TO_FIELD.setdefault(_key(_n), _field)


def phone_digits(s: str | None) -> str:
    return re.sub(r"\D", "", s or "")


def _looks_like_header(cells: list[str]) -> bool:
    """A row is the header if two+ of its cells map to known fields (avoids the report title rows)."""
    hits = sum(1 for c in cells if _key(c) in _HEADER_TO_FIELD)
    return hits >= 2


# When an export has NO Company column (e.g. QuickBooks' "Customer Contact List"), we
# infer commercial-vs-residential from the name. A word in this set, a digit, or a
# corporate punctuation cue (&, /, :, parentheses) marks a business. Everything else is
# treated as a person — imperfect by nature; the preview's untick lets the owner correct.
COMPANY_TOKENS: frozenset[str] = frozenset("""
inc incorporated ltd limited llc llp lp corp corporation co company holdings holding realty
property properties management mgmt strata rentals rental ventures enterprises productions
services service group construction contracting contractors contractor developments development
builders building homes roofing plumbing electric electrical hvac refrigeration mechanical
foundation ministries ministry society association associates partners partnership resort
logistics storage apartments apartment towers tower estates estate systems restorations
landscaping cleaning painting moving towing auto motors automotive glass granite cabinets
floors flooring renovations reno excavating paving fencing decks windows doors insulation
drywall concrete masonry welding appliance catering events studio studios gallery boutique
salon spa fitness gym bakery deli market grocery pharmacy bank insurance mortgage dental
chiropractic physio veterinary clinic hospital lodge inn suites motel hotel rv marina winery
brewing brewery distillery cafe restaurant pub bistro university college school church temple
depot store shop centre center trust bc canada national international global solutions
industries manufacturing supply supplies equipment rentals technologies technology consulting
""".split())

_CO_PUNCT = re.compile(r"[&:/]|\bc/o\b|\(", re.I)


def guess_kind(name: str | None) -> str:
    """A hard company signal from a display name: a company word, a digit (numbered
    companies / 1-800), or corporate punctuation (&, c/o, parens). Else 'residential'."""
    s = (name or "").strip()
    if not s:
        return "residential"
    if any(ch.isdigit() for ch in s) or _CO_PUNCT.search(s):   # numbered cos, 1-800, "c/o", "A & B"
        return "company"
    words = {w for w in re.findall(r"[A-Za-z]+", s.lower())}
    if words & COMPANY_TOKENS:
        return "company"
    return "residential"


def infer_kind(display: str, full_name: str = "") -> str:
    """Company-vs-residential when there's no Company column. QuickBooks gives individuals
    a Full Name and companies a company-style display, but the data is uneven (companies
    can carry a contact's Full Name; some people lack one). So: a hard company signal wins;
    otherwise a short name (<=3 words) is a person and a longer one is an organisation."""
    if guess_kind(display or full_name) == "company":
        return "company"
    src = (full_name or display).split()
    return "residential" if 1 <= len(src) <= 3 else "company"


def _cell(v) -> str:
    return "" if v is None else str(v).strip()


def _records_from_grid(grid: list[list]) -> list[dict]:
    """Turn a raw grid (CSV or worksheet) into {field: value} dicts: drop blank lines,
    find the header row by alias, map columns, keep non-empty cells."""
    rows = [r for r in grid if any(_cell(c) for c in r)]
    if not rows:
        return []
    h_idx = next((i for i, r in enumerate(rows) if _looks_like_header([_cell(c) for c in r])), 0)
    fields = [_HEADER_TO_FIELD.get(_key(_cell(c))) for c in rows[h_idx]]
    out: list[dict] = []
    for r in rows[h_idx + 1:]:
        rec: dict[str, str] = {}
        for col, val in zip(fields, r):
            s = _cell(val)
            if col and s:
                rec[col] = s
        if rec:
            out.append(rec)
    return out


def parse_csv(text: str) -> list[dict]:
    """Parse a QuickBooks CSV export -> {field: value} rows (skips the report preamble)."""
    if text and text[0] == "﻿":       # strip BOM
        text = text[1:]
    return _records_from_grid([list(r) for r in csv.reader(io.StringIO(text))])


def parse_xlsx(source, sheet: str | None = None) -> list[dict]:
    """Parse a QuickBooks Excel export (path or file-like). openpyxl is imported lazily
    so CSV-only use needs no Excel dependency."""
    import openpyxl
    wb = openpyxl.load_workbook(source, read_only=True, data_only=True)
    ws = wb[sheet] if sheet else wb.active
    grid = [list(r) for r in ws.iter_rows(values_only=True)]
    wb.close()
    return _records_from_grid(grid)


def parse_file(path) -> list[dict]:
    """Parse a QuickBooks export by extension (.xlsx/.xls -> Excel, else CSV)."""
    if str(path).lower().endswith((".xlsx", ".xlsm", ".xls")):
        return parse_xlsx(path)
    return parse_csv(Path(path).read_text(encoding="utf-8-sig"))


def _split_name(raw: str) -> tuple[str, str]:
    """'Last, First' or 'First Last' -> (first, last)."""
    raw = (raw or "").strip()
    if not raw:
        return "", ""
    if "," in raw:
        last, _, first = raw.partition(",")
        return first.strip(), last.strip()
    parts = raw.split()
    if len(parts) == 1:
        return parts[0], ""
    return " ".join(parts[:-1]), parts[-1]


def _address(row: dict) -> str:
    """Stitch whatever address parts are present (Excel cells can hold multi-line
    addresses -> collapse newlines to a single line). A single 'Full Address' column comes
    through as `address`; QuickBooks Desktop's split billing columns get joined."""
    bits = [row.get("address"), row.get("city"), row.get("province"), row.get("postal")]
    joined = ", ".join(b for b in bits if b)
    return re.sub(r"\s*[\r\n]+\s*", ", ", joined).strip(", ").strip()


# QuickBooks' "Phone Numbers" column can hold several labelled numbers; keep the first.
_PHONE_LABEL = re.compile(r"^\s*(mobile|phone|cell|work|home|main|fax|tel|telephone|office)\s*[:.]?\s*", re.I)
# DB column caps (String lengths) — values are truncated to fit on import.
_LIMITS = {"first": 120, "last": 120, "co": 180, "name": 180, "contact": 120, "email": 180, "addr": 255}


def _first_phone(raw: str | None) -> str | None:
    """First number from a multi-number 'Phone Numbers' cell, label stripped, capped at 40."""
    if not raw:
        return None
    seg = re.split(r"[;,\n]", raw)[0]
    seg = _PHONE_LABEL.sub("", seg).strip()
    return seg[:40] or None


def _fit(rec: dict | None) -> dict | None:
    """Make a classified record DB-safe: normalise phone, truncate to column limits."""
    if rec is None:
        return None
    rec["phone"] = _first_phone(rec.get("phone"))
    for k, n in _LIMITS.items():
        if rec.get(k):
            rec[k] = rec[k][:n]
    return rec


def classify(row: dict) -> dict | None:
    """Normalise one parsed row into a residential or company customer record.
    Returns None if the row has no usable identity."""
    company = (row.get("company") or "").strip()
    name = (row.get("customer") or "").strip()
    full = (row.get("full_name") or "").strip()
    first = (row.get("first") or "").strip()
    last = (row.get("last") or "").strip()
    phone = (row.get("phone") or "").strip()
    email = (row.get("email") or "").strip()
    addr = _address(row)
    display = name or full

    # (1) An explicit Company column is authoritative -> commercial.
    if company:
        contact = name if (name and _key(name) != _key(company)) else (full or f"{first} {last}".strip() or None)
        return _fit({"kind": "company", "co": company, "contact": contact or None,
                     "phone": phone or None, "email": email or None, "addr": addr or None})

    # (2) No Company column (QuickBooks Contact List): infer from name + Full Name.
    if not (first or last) and display and infer_kind(display, full) == "company":
        contact = full if (full and _key(full) != _key(display)) else None
        return _fit({"kind": "company", "co": display, "contact": contact,
                     "phone": phone or None, "email": email or None, "addr": addr or None})

    # (3) Residential — split the person name (prefer an explicit Full Name column).
    if not (first or last):
        first, last = _split_name(full or name)
    if not (first or last or phone or email):
        return None
    return _fit({"kind": "residential", "first": first or None, "last": last or None,
                 "phone": phone or None, "email": email or None, "addr": addr or None})


def residential_key(r: dict) -> str:
    """Dedupe identity: digits phone (>=7) else email else first|last (matches the booking screen)."""
    d = phone_digits(r.get("phone"))
    if len(d) >= 7:
        return "p:" + d
    if r.get("email"):
        return "e:" + r["email"].strip().lower()
    return "n:" + f"{r.get('first') or ''}|{r.get('last') or ''}".lower().strip()


def company_key(r: dict) -> str:
    return "c:" + (r.get("co") or "").strip().lower()


def _existing_residential_keys(db: DbSession, brand: Brand) -> set[str]:
    keys: set[str] = set()
    for c in db.scalars(select(ResidentialCustomer).where(ResidentialCustomer.brand == brand)):
        keys.add(residential_key({"phone": c.phone, "email": c.email, "first": c.first, "last": c.last}))
    return keys


def _existing_company_keys(db: DbSession, brand: Brand) -> set[str]:
    return {company_key({"co": c.co}) for c in
            db.scalars(select(CompanyCustomer).where(CompanyCustomer.brand == brand))}


def build_preview(db: DbSession, brand: Brand, rows: list[dict]) -> dict:
    """Split classified rows into new vs duplicate (vs the DB and within the batch)."""
    have_res = _existing_residential_keys(db, brand)
    have_co = _existing_company_keys(db, brand)
    seen: set[str] = set()
    res_new, res_dup, co_new, co_dup, skipped = [], [], [], [], []
    for raw in rows:
        rec = classify(raw)
        if rec is None:
            skipped.append({"row": raw, "reason": "no name / phone / email"})
            continue
        if rec["kind"] == "company":
            k = company_key(rec)
            rec = {**rec, "key": k}
            if k in have_co or k in seen:
                co_dup.append(rec)
            else:
                co_new.append(rec)
                seen.add(k)
        else:
            k = residential_key(rec)
            rec = {**rec, "key": k}
            if k in have_res or k in seen:
                res_dup.append(rec)
            else:
                res_new.append(rec)
                seen.add(k)
    return {
        "residential": {"new": res_new, "duplicate": res_dup},
        "company": {"new": co_new, "duplicate": co_dup},
        "skipped": skipped,
        "counts": {"residential_new": len(res_new), "residential_dup": len(res_dup),
                   "company_new": len(co_new), "company_dup": len(co_dup), "skipped": len(skipped)},
    }


def apply_import(db: DbSession, brand: Brand, rows: list[dict],
                 skip_keys: set[str] | None = None) -> dict:
    """Insert the new (non-duplicate, not-unticked) customers. Dedupe is by phone/email,
    so re-running the same export inserts nothing. `skip_keys` = the untick set."""
    skip = skip_keys or set()
    prev = build_preview(db, brand, rows)
    added_res = added_co = 0
    for rec in prev["residential"]["new"]:
        if rec["key"] in skip:
            continue
        db.add(ResidentialCustomer(
            brand=brand, first=rec.get("first"), last=rec.get("last"),
            phone=rec.get("phone"), email=rec.get("email"), addr=rec.get("addr")))
        added_res += 1
    for rec in prev["company"]["new"]:
        if rec["key"] in skip:
            continue
        db.add(CompanyCustomer(
            brand=brand, co=rec["co"], name=rec["co"], contact=rec.get("contact"),
            phone=rec.get("phone"), email=rec.get("email"), addr=rec.get("addr"),
            accounts=[], src=CustomerSource.qb))
        added_co += 1
    db.commit()
    return {
        "added_residential": added_res, "added_company": added_co,
        "skipped_duplicates": prev["counts"]["residential_dup"] + prev["counts"]["company_dup"],
        "unusable_rows": prev["counts"]["skipped"],
    }
