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

from sqlalchemy import or_, select
from sqlalchemy.orm import Session as DbSession

from app.models.customer import CompanyCustomer, ResidentialCustomer
from app.models.enums import Brand, CustomerSource

# field -> accepted header names (compared case/space/punctuation-insensitively).
COLUMN_ALIASES: dict[str, list[str]] = {
    "customer": ["customer", "customer full name", "display name", "name", "full name"],
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


def parse_csv(text: str) -> list[dict]:
    """Rows as {field: value} dicts. Skips QuickBooks' title/preamble rows, maps by alias."""
    if text and text[0] == "﻿":       # strip BOM
        text = text[1:]
    reader = csv.reader(io.StringIO(text))
    rows = [r for r in reader if any((c or "").strip() for c in r)]  # drop blank lines
    if not rows:
        return []
    # find the header row (first row that looks like column headings)
    h_idx = next((i for i, r in enumerate(rows) if _looks_like_header(r)), 0)
    header = rows[h_idx]
    fields = [_HEADER_TO_FIELD.get(_key(c)) for c in header]
    out: list[dict] = []
    for r in rows[h_idx + 1:]:
        rec: dict[str, str] = {}
        for col, val in zip(fields, r):
            if col and (val or "").strip():
                rec[col] = val.strip()
        if rec:
            out.append(rec)
    return out


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
    """Stitch whatever address parts are present. A single 'Full Address' column comes
    through as `address` alone; QuickBooks Desktop's split billing columns get joined."""
    bits = [row.get("address"), row.get("city"), row.get("province"), row.get("postal")]
    return ", ".join(b for b in bits if b)


def classify(row: dict) -> dict | None:
    """Normalise one parsed row into a residential or company customer record.
    Returns None if the row has no usable identity."""
    company = (row.get("company") or "").strip()
    name = (row.get("customer") or "").strip()
    first = (row.get("first") or "").strip()
    last = (row.get("last") or "").strip()
    phone = (row.get("phone") or "").strip()
    email = (row.get("email") or "").strip()
    addr = _address(row)

    # A company row: any non-empty Company column. QuickBooks fills Company for a business
    # (often echoing it into the display name too), so a filled Company => commercial. The
    # contact person is the display name only when it differs from the company name.
    if company:
        contact = name if (name and _key(name) != _key(company)) else (f"{first} {last}".strip() or None)
        return {
            "kind": "company", "co": company, "contact": contact or None,
            "phone": phone or None, "email": email or None, "addr": addr or None,
        }

    if not (first or last) and name:
        first, last = _split_name(name)
    if not (first or last or phone or email):
        return None
    return {
        "kind": "residential", "first": first or None, "last": last or None,
        "phone": phone or None, "email": email or None, "addr": addr or None,
    }


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
