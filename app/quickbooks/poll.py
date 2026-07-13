"""QuickBooks auto-poll — sync every brand whose owner turned auto-sync ON (WS4, READ-ONLY).

Run on a schedule by the Render Cron Job (`scripts/qbo_poll.py`). It's the exact same read-only
sync as the manual "Sync now" button, just fanned out over all opted-in brands. Per-brand errors
are caught so one bad connection never blocks the others. Never writes to QBO, never charges.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.models.qbo import QboConnection
from app.quickbooks.sync import sync_brand


def poll_all(db: DbSession) -> list[dict]:
    """Run sync_brand for every ACTIVE connection with auto_sync_enabled=True. Returns one result
    dict per brand (brand key added). A brand that raises is captured, not propagated."""
    conns = db.scalars(select(QboConnection).where(
        QboConnection.active.is_(True), QboConnection.auto_sync_enabled.is_(True))).all()
    results: list[dict] = []
    for conn in conns:
        try:
            res = sync_brand(db, conn.brand)
        except Exception as e:  # noqa: BLE001 — isolate one brand's failure from the rest
            db.rollback()
            res = {"ok": False, "reason": f"exception: {e}"}
        results.append({**res, "brand": conn.brand.value})
    return results
