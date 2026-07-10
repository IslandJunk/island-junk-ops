"""Day Board API — reads the TEST calendar into a truck-by-truck dispatch view."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_employee
from app.db.session import get_db
from app.dispatch.day_board import read_day
from app.models.employee import Employee
from app.models.enums import Brand

router = APIRouter(prefix="/day-board", tags=["dispatch"])


@router.get("")
def day_board(
    on: date = Query(..., description="Local date, YYYY-MM-DD"),
    brand: Brand = Brand.victoria,
    db: DbSession = Depends(get_db),
    _emp: Employee = Depends(get_current_employee),
) -> dict:
    return read_day(db, brand, on)
