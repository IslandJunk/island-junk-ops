"""Sync API — persists a synced localStorage key into Postgres via its handler."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_current_employee
from app.db.session import get_db
from app.models.employee import Employee
from app.models.enums import Brand
from app.web.sync_handlers import HANDLERS

router = APIRouter(prefix="/sync", tags=["sync"])


class SyncIn(BaseModel):
    key: str
    value: str  # the raw localStorage JSON string


@router.post("")
def sync(body: SyncIn, db: DbSession = Depends(get_db),
         emp: Employee = Depends(get_current_employee)) -> dict:
    handler = HANDLERS.get(body.key)
    if handler is None:
        return {"synced": False, "reason": f"key '{body.key}' is not synced"}
    try:
        data = json.loads(body.value)
    except (ValueError, TypeError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "value is not valid JSON")
    # brand follows the signed-in user (owner has no fixed brand -> default victoria).
    brand = emp.brand or Brand.victoria
    result = handler(db, brand, data, emp)
    return {"synced": True, "key": body.key, **result}
