"""Yard-processing save — dedicated endpoint for the rich close-out record the
prototype keeps in memory (not a localStorage sync key)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from app.api.deps import active_brand_for, get_current_employee
from app.db.session import get_db
from app.models.employee import Employee
from app.web.sync_handlers import apply_yard_processing

router = APIRouter(prefix="/yard-processing", tags=["yard"])


class YardIn(BaseModel):
    records: list[dict]


@router.post("")
def save(body: YardIn, request: Request, db: DbSession = Depends(get_db),
         emp: Employee = Depends(get_current_employee)) -> dict:
    return apply_yard_processing(db, active_brand_for(request, emp), body.records, emp)
