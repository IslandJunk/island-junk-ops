"""Background finish-link poll — stamps the "Finish this booking in the app" link onto hand-made
TEST-calendar events on an interval, so the manager sees it in Google Calendar without anyone having
to open that day's Day Board first (`read_day` only stamps the day it reads).

Runs INSIDE the web service (same pattern as the QBO auto-sync loop — no separate cron service to
configure). The write is the same guarded, description-only stamp the board already does: TEST
calendar ONLY (never a live dispatch calendar) and never the title/colour/time, so the status colour
Make.com reads is untouched. Best-effort: it sleeps first (so boot is never blocked), it is a no-op
when `finish_link_poll_enabled` is off, and it never dies on an error.
"""
from __future__ import annotations

import asyncio

from app.core.config import settings
from app.db.session import new_session
from app.dispatch.day_board import poll_finish_links


def _run_once() -> dict:
    db = new_session()
    try:
        return poll_finish_links(db)
    finally:
        db.close()


async def finish_link_poll_loop() -> None:
    """Every interval, stamp the next N days' hand-made events. The blocking calendar/DB work runs in
    a worker thread so it never stalls the web server, and any error is swallowed so the loop lives on."""
    while True:
        await asyncio.sleep(settings.finish_link_poll_seconds)
        if not settings.finish_link_poll_enabled:
            continue   # toggled off — stay alive, do nothing
        try:
            r = await asyncio.to_thread(_run_once)
            if r.get("stamped"):
                print(f"finish-link-poll: {r}")   # log only when a link was actually stamped
        except Exception as e:  # noqa: BLE001 — the loop must never crash the app
            print(f"finish-link-poll error: {e!r}")
