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


@router.get("/search")
def search(request: Request, q: str = "", limit: int = 40,
           db: DbSession = Depends(get_db), emp: Employee = Depends(require_manager)) -> dict:
    """Owner + manager: one search box across residential / commercial / PM customers. Empty q browses
    the first N of each (PM buildings only surface on an actual query — there can be a lot of them)."""
    brand = active_brand_for(request, emp)
    limit = max(1, min(limit, 100))
    q = (q or "").strip()
    like = f"%{q}%"
    out: list[dict] = []

    rs = select(ResidentialCustomer).where(ResidentialCustomer.brand == brand)
    if q:
        rs = rs.where(or_(
            ResidentialCustomer.first.ilike(like), ResidentialCustomer.last.ilike(like),
            func.concat(func.coalesce(ResidentialCustomer.first, ""), " ",
                        func.coalesce(ResidentialCustomer.last, "")).ilike(like),
            ResidentialCustomer.phone.ilike(like), ResidentialCustomer.email.ilike(like),
            ResidentialCustomer.addr.ilike(like)))
    out += [_res_row(c) for c in db.scalars(rs.order_by(ResidentialCustomer.first).limit(limit)).all()]

    cs = select(CompanyCustomer).where(CompanyCustomer.brand == brand)
    if q:
        cs = cs.where(or_(CompanyCustomer.co.ilike(like), CompanyCustomer.name.ilike(like),
                          CompanyCustomer.contact.ilike(like), CompanyCustomer.phone.ilike(like),
                          CompanyCustomer.email.ilike(like), CompanyCustomer.addr.ilike(like)))
    out += [_co_row(c) for c in db.scalars(cs.order_by(CompanyCustomer.co).limit(limit)).all()]

    ps = select(PmCompany).where(PmCompany.brand == brand)
    if q:
        ps = ps.where(or_(PmCompany.nm.ilike(like), PmCompany.contact.ilike(like),
                          PmCompany.phone.ilike(like), PmCompany.email.ilike(like), PmCompany.addr.ilike(like)))
    out += [_pmco_row(c) for c in db.scalars(ps.order_by(PmCompany.nm).limit(limit)).all()]

    if q:  # buildings are the leaf sites — only when searching (there can be many)
        bs = select(PmBuilding).where(PmBuilding.brand == brand).where(or_(
            PmBuilding.name.ilike(like), PmBuilding.address.ilike(like),
            PmBuilding.contact.ilike(like), PmBuilding.phone.ilike(like), PmBuilding.email.ilike(like)))
        out += [_pmb_row(c) for c in db.scalars(bs.limit(limit)).all()]

    out.sort(key=lambda r: (r["name"] or "").lower())
    return {"brand": brand.value, "count": len(out), "results": out[: limit * 2]}


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
