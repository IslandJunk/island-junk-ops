"""In-app auto-sync scheduler (WS4) — polls QBO for auto-sync-enabled brands on an interval.

Runs INSIDE the web service (no separate cron service to configure), so turning on the Owner-Hub
auto-sync toggle is all it takes — no Render setup. The loop calls poll_all every
POLL_INTERVAL_SECONDS, which is a no-op for any brand whose toggle is OFF. Read-only; never charges.
Best-effort: it sleeps first (so boot is never blocked) and never dies on an error.
"""
from __future__ import annotations

import asyncio

from app.db.session import new_session
from app.quickbooks.poll import poll_all

POLL_INTERVAL_SECONDS = 900   # 15 minutes


def _run_once() -> list[dict]:
    db = new_session()
    try:
        return poll_all(db)
    finally:
        db.close()


async def qbo_poll_loop() -> None:
    """Every interval, sync all auto-sync-enabled brands. The blocking sync runs in a worker
    thread so it never stalls the web server, and any error is swallowed so the loop lives on."""
    while True:
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        try:
            for r in await asyncio.to_thread(_run_once):
                if r.get("started") or r.get("paid"):
                    print(f"qbo-auto-sync: {r}")   # log only when something actually changed
        except Exception as e:  # noqa: BLE001 — the loop must never crash the app
            print(f"qbo-auto-sync error: {e!r}")
