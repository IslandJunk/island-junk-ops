"""Yard-processing save — dedicated endpoint for the rich close-out record the
prototype keeps in memory (not a localStorage sync key)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_employee
from app.db.session import get_db
from app.models.employee import Employee
from app.models.enums import Brand
from app.web.sync_handlers import apply_yard_processing

router = APIRouter(prefix="/yard-processing", tags=["yard"])


class YardIn(BaseModel):
    records: list[dict]


@router.post("")
def save(body: YardIn, db: DbSession = Depends(get_db),
         emp: Employee = Depends(get_current_employee)) -> dict:
    brand = emp.brand or Brand.victoria
    return apply_yard_processing(db, brand, body.records, emp)
