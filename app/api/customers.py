"""Customer import (§13) — owner-only. Upload a QuickBooks Customer Contact List,
preview new-vs-duplicate (matched on phone/email), then apply the ticked rows.
No charging/invoicing here (guardrail §2)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session as DbSession

from app.api.deps import active_brand_for, get_current_employee, require_manager
from app.auth.guards import is_owner
from app.customers.qb_import import apply_import, build_preview, parse_csv
from app.db.session import get_db
from app.models.customer import CompanyCustomer, PmBuilding, PmCompany, ResidentialCustomer
from app.models.employee import Employee
from app.models.enums import Brand

router = APIRouter(prefix="/customers", tags=["customers"])


class ImportIn(BaseModel):
    csv: str | None = None
    rows: list[dict] | None = None
    skip: list[str] | None = None   # dedupe keys the owner unticked in the preview


def _owner_or_403(request: Request, emp: Employee) -> Brand:
    if not is_owner(emp):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Owner access required")
    return active_brand_for(request, emp)


def _rows(body: ImportIn) -> list[dict]:
    if body.rows is not None:
        return body.rows
    if body.csv is not None:
        return parse_csv(body.csv)
    raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Provide `csv` or `rows`")


@router.post("/import/preview")
def import_preview(body: ImportIn, request: Request, db: DbSession = Depends(get_db),
                   emp: Employee = Depends(get_current_employee)) -> dict:
    brand = _owner_or_403(request, emp)
    return build_preview(db, brand, _rows(body))


@router.post("/import/apply")
def import_apply(body: ImportIn, request: Request, db: DbSession = Depends(get_db),
                 emp: Employee = Depends(get_current_employee)) -> dict:
    brand = _owner_or_403(request, emp)
    return apply_import(db, brand, _rows(body), skip_keys=set(body.skip or []))


@router.get("/summary")
def summary(request: Request, db: DbSession = Depends(get_db),
            emp: Employee = Depends(get_current_employee)) -> dict:
    brand = _owner_or_403(request, emp)

    def n(model) -> int:
        return db.scalar(select(func.count()).select_from(model).where(model.brand == brand)) or 0

    return {"brand": brand.value, "residential": n(ResidentialCustomer),
            "company": n(CompanyCustomer), "pm_companies": n(PmCompany), "pm_buildings": n(PmBuilding)}


# ── The Customers database screen (owner + manager): unified search + edit ──────────────────────

def _res_row(c: ResidentialCustomer) -> dict:
    return {"kind": "residential", "id": str(c.id), "type_label": "Residential",
            "name": " ".join(x for x in [c.first, c.last] if x) or "(no name)",
            "first": c.first, "last": c.last, "company": None, "contact": None,
            "phone": c.phone, "email": c.email, "address": c.addr}


def _co_row(c: CompanyCustomer) -> dict:
    return {"kind": "company", "id": str(c.id), "type_label": "Commercial",
            "name": c.co or "(no name)", "first": None, "last": None, "company": c.co, "contact": c.contact,
            "phone": c.phone, "email": c.email, "address": c.addr}


def _pmco_row(c: PmCompany) -> dict:
    return {"kind": "pm_company", "id": str(c.id), "type_label": "Property mgmt",
            "name": c.nm or "(no name)", "first": None, "last": None, "company": c.nm, "contact": c.contact,
            "phone": c.phone, "email": c.email, "address": c.addr}


def _pmb_row(c: PmBuilding) -> dict:
    return {"kind": "pm_building", "id": str(c.id), "type_label": "PM site",
            "name": c.name or "(no name)", "first": None, "last": None, "company": c.name, "contact": c.contact,
            "phone": c.phone, "email": c.email, "address": c.address}


_RES_TYPES = {"all", "residential", "res"}
_CO_TYPES = {"all", "commercial", "company", "co"}
_PM_TYPES = {"all", "pm", "property_mgmt", "pm_company"}


@router.get("/search")
def search(request: Request, q: str = "", type: str = "all", limit: int = 40,
           db: DbSession = Depends(get_db), emp: Employee = Depends(require_manager)) -> dict:
    """Owner + manager: search customers, optionally filtered to one `type` tab
    (all | residential | commercial | pm). Empty q browses the first N; PM buildings only surface on
    an actual query (there can be a lot of them)."""
    brand = active_brand_for(request, emp)
    limit = max(1, min(limit, 100))
    q = (q or "").strip()
    want = (type or "all").strip().lower()
    like = f"%{q}%"
    out: list[dict] = []

    if want in _RES_TYPES:
        rs = select(ResidentialCustomer).where(ResidentialCustomer.brand == brand)
        if q:
            rs = rs.where(or_(
                ResidentialCustomer.first.ilike(like), ResidentialCustomer.last.ilike(like),
                func.concat(func.coalesce(ResidentialCustomer.first, ""), " ",
                            func.coalesce(ResidentialCustomer.last, "")).ilike(like),
                ResidentialCustomer.phone.ilike(like), ResidentialCustomer.email.ilike(like),
                ResidentialCustomer.addr.ilike(like)))
        out += [_res_row(c) for c in db.scalars(rs.order_by(ResidentialCustomer.first).limit(limit)).all()]

    if want in _CO_TYPES:
        cs = select(CompanyCustomer).where(CompanyCustomer.brand == brand)
        if q:
            cs = cs.where(or_(CompanyCustomer.co.ilike(like), CompanyCustomer.name.ilike(like),
                              CompanyCustomer.contact.ilike(like), CompanyCustomer.phone.ilike(like),
                              CompanyCustomer.email.ilike(like), CompanyCustomer.addr.ilike(like)))
        out += [_co_row(c) for c in db.scalars(cs.order_by(CompanyCustomer.co).limit(limit)).all()]

    if want in _PM_TYPES:
        ps = select(PmCompany).where(PmCompany.brand == brand)
        if q:
            ps = ps.where(or_(PmCompany.nm.ilike(like), PmCompany.contact.ilike(like),
                              PmCompany.phone.ilike(like), PmCompany.email.ilike(like), PmCompany.addr.ilike(like)))
        out += [_pmco_row(c) for c in db.scalars(ps.order_by(PmCompany.nm).limit(limit)).all()]
        if q:  # buildings are the leaf sites — only when searching
            bs = select(PmBuilding).where(PmBuilding.brand == brand).where(or_(
                PmBuilding.name.ilike(like), PmBuilding.address.ilike(like),
                PmBuilding.contact.ilike(like), PmBuilding.phone.ilike(like), PmBuilding.email.ilike(like)))
            out += [_pmb_row(c) for c in db.scalars(bs.limit(limit)).all()]

    out.sort(key=lambda r: (r["name"] or "").lower())
    return {"brand": brand.value, "type": want, "count": len(out), "results": out[: limit * 2]}


class CustomerPatch(BaseModel):
    first: str | None = None
    last: str | None = None
    company: str | None = None
    contact: str | None = None
    phone: str | None = None
    email: str | None = None
    address: str | None = None


_KIND_MODEL = {"residential": ResidentialCustomer, "company": CompanyCustomer,
               "pm_company": PmCompany, "pm_building": PmBuilding}
# per kind: incoming patch field -> model attribute
_KIND_FIELDS = {
    "residential": {"first": "first", "last": "last", "phone": "phone", "email": "email", "address": "addr"},
    "company": {"company": "co", "contact": "contact", "phone": "phone", "email": "email", "address": "addr"},
    "pm_company": {"company": "nm", "contact": "contact", "phone": "phone", "email": "email", "address": "addr"},
    "pm_building": {"company": "name", "contact": "contact", "phone": "phone", "email": "email", "address": "address"},
}


@router.patch("/{kind}/{cid}")
def update_customer(kind: str, cid: str, body: CustomerPatch, request: Request,
                    db: DbSession = Depends(get_db), emp: Employee = Depends(require_manager)) -> dict:
    """Owner + manager: edit a customer's name / contact / phone / email / address (brand-scoped)."""
    brand = active_brand_for(request, emp)
    model = _KIND_MODEL.get(kind)
    if model is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown customer kind")
    try:
        oid = uuid.UUID(cid)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "customer not found")
    c = db.get(model, oid)
    if c is None or c.brand != brand:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "customer not found")
    patch = body.model_dump(exclude_unset=True)
    for field, attr in _KIND_FIELDS[kind].items():
        if field in patch:
            setattr(c, attr, (patch[field] or None) if isinstance(patch[field], str) else patch[field])
    db.commit()
    return {"ok": True, "kind": kind, "id": cid}


class ConvertIn(BaseModel):
    to: str   # "commercial" | "residential"


@router.post("/{kind}/{cid}/convert")
def convert_customer(kind: str, cid: str, body: ConvertIn, request: Request,
                     db: DbSession = Depends(get_db), emp: Employee = Depends(require_manager)) -> dict:
    """Owner + manager: reclassify a customer between RESIDENTIAL and COMMERCIAL (fix a bad import).
    Recreates the record in the other table with a best-effort field mapping, deletes the original,
    and returns the new kind + id. Name mapping is imprecise (person name ↔ company name), so the
    editor can be reopened to tidy fields afterward."""
    brand = active_brand_for(request, emp)
    to = (body.to or "").strip().lower()
    try:
        oid = uuid.UUID(cid)
    except ValueError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "customer not found")

    if kind == "residential" and to in ("commercial", "company"):
        c = db.get(ResidentialCustomer, oid)
        if c is None or c.brand != brand:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "customer not found")
        name = " ".join(x for x in [c.first, c.last] if x).strip() or "(unnamed)"
        new = CompanyCustomer(brand=brand, co=name, name=name, addr=c.addr, phone=c.phone,
                              email=c.email, contact=None, accounts=[])
        db.add(new); db.delete(c); db.flush()
        new_kind, new_id = "company", new.id
    elif kind == "company" and to in ("residential", "res"):
        c = db.get(CompanyCustomer, oid)
        if c is None or c.brand != brand:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "customer not found")
        parts = (c.co or "").split()
        first = parts[0] if parts else (c.co or None)
        last = " ".join(parts[1:]) if len(parts) > 1 else None
        new = ResidentialCustomer(brand=brand, first=first, last=last, phone=c.phone,
                                  email=c.email, addr=c.addr)
        db.add(new); db.delete(c); db.flush()
        new_kind, new_id = "residential", new.id
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "only residential ↔ commercial conversion is supported")

    db.commit()
    return {"ok": True, "kind": new_kind, "id": str(new_id)}


class CoLocationIn(BaseModel):
    company: str
    location: str
    address: str


@router.post("/company-location")
def save_company_location(body: CoLocationIn, request: Request, db: DbSession = Depends(get_db),
                          emp: Employee = Depends(require_manager)) -> dict:
    """Remember a commercial account's job SITE: `{company, location, address}`.

    Called after a commercial booking, so next time the manager picks that saved location the job
    address fills itself instead of being retyped. Matched on the company name the same
    case-insensitive way the sync upsert dedupes. Additive only: the location is appended to
    `accounts` if new, and `account_addrs[location]` is set — no other site is touched, and this
    never creates a company (an unknown name is reported back, not silently invented).
    """
    brand = active_brand_for(request, emp)
    company = (body.company or "").strip()
    location = (body.location or "").strip()
    address = (body.address or "").strip()
    if not (company and location and address):
        return {"saved": False, "detail": "company, location and address are all required"}

    c = db.scalar(
        select(CompanyCustomer).where(
            CompanyCustomer.brand == brand, func.lower(CompanyCustomer.co) == company.lower()
        )
    )
    if c is None:
        return {"saved": False, "detail": f"no commercial account named {company!r}"}

    accounts = list(c.accounts or [])
    is_new = not any((a or "").strip().lower() == location.lower() for a in accounts)
    if is_new:
        accounts.append(location)
        c.accounts = accounts
    # dict must be REPLACED (not mutated) for SQLAlchemy to flag the JSONB column as dirty
    c.account_addrs = {**(c.account_addrs or {}), location: address}
    db.commit()
    return {"saved": True, "company": c.co, "location": location, "new_location": is_new}
