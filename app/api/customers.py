"""Customer import (§13) — owner-only. Upload a QuickBooks Customer Contact List,
preview new-vs-duplicate (matched on phone/email), then apply the ticked rows.
No charging/invoicing here (guardrail §2)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_employee
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


def _owner_or_403(emp: Employee) -> Brand:
    if not is_owner(emp):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Owner access required")
    return emp.brand or Brand.victoria


def _rows(body: ImportIn) -> list[dict]:
    if body.rows is not None:
        return body.rows
    if body.csv is not None:
        return parse_csv(body.csv)
    raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Provide `csv` or `rows`")


@router.post("/import/preview")
def import_preview(body: ImportIn, db: DbSession = Depends(get_db),
                   emp: Employee = Depends(get_current_employee)) -> dict:
    brand = _owner_or_403(emp)
    return build_preview(db, brand, _rows(body))


@router.post("/import/apply")
def import_apply(body: ImportIn, db: DbSession = Depends(get_db),
                 emp: Employee = Depends(get_current_employee)) -> dict:
    brand = _owner_or_403(emp)
    return apply_import(db, brand, _rows(body), skip_keys=set(body.skip or []))


@router.get("/summary")
def summary(db: DbSession = Depends(get_db),
            emp: Employee = Depends(get_current_employee)) -> dict:
    brand = _owner_or_403(emp)

    def n(model) -> int:
        return db.scalar(select(func.count()).select_from(model).where(model.brand == brand)) or 0

    return {"brand": brand.value, "residential": n(ResidentialCustomer),
            "company": n(CompanyCustomer), "pm_companies": n(PmCompany), "pm_buildings": n(PmBuilding)}
