"""Sync API — persists a synced localStorage key into Postgres via its handler."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from app.api.deps import active_brand_for, get_current_employee
from app.auth.guards import is_owner
from app.db.session import get_db
from app.models.employee import Employee
from app.models.enums import Brand
from app.web.sync_handlers import HANDLERS

router = APIRouter(prefix="/sync", tags=["sync"])


class SyncIn(BaseModel):
    key: str
    value: str            # the raw localStorage JSON string
    brand: Brand | None = None  # the brand the PAGE was served with (owner may switch)


@router.post("")
def sync(body: SyncIn, request: Request, db: DbSession = Depends(get_db),
         emp: Employee = Depends(get_current_employee)) -> dict:
    handler = HANDLERS.get(body.key)
    if handler is None:
        return {"synced": False, "reason": f"key '{body.key}' is not synced"}
    try:
        data = json.loads(body.value)
    except (ValueError, TypeError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "value is not valid JSON")
    # Write to the brand the PAGE was serving (never-mix, §15): the owner may write any brand
    # they were viewing; crew are hard-locked to their own brand regardless of what's sent.
    if is_owner(emp) and body.brand is not None:
        brand = body.brand
    else:
        brand = active_brand_for(request, emp)
    result = handler(db, brand, data, emp)
    return {"synced": True, "key": body.key, "brand": brand.value, **result}
