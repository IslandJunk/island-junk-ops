"""Day Board reader — mirrors the manager's Google Calendar into a truck-by-truck
dispatch view. This is the READ side (the app only writes at booking).

Pipeline, in order (scheduling spec):
  1. Read the day's events, ordered by start time (= the manual vertical stack — spike).
  2. Drop `#` manager notes entirely (§4).
  3. Group by colour -> truck / status / unassigned via the colour map (§1).
  4. Route order = the stacked order within each truck (§2).
  5. Time comes from the HEADLINE, never the slot (§3).

Each job is enriched from its linked Postgres Job row (customer/address/type/scope) —
the calendar gives colour + order + time; the DB gives the rich details.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app.dispatch.calendar_read import is_manager_note, manager_notes_from_desc, parse_headline_time
from app.integrations import gcal
from app.models.colour_map import ColourMap
from app.models.enums import Brand, ColourKind
from app.models.job import Job


def _job_view(ev: dict, colour: ColourMap | None, job: Job | None) -> dict:
    start, end = parse_headline_time(ev.get("summary", ""))
    return {
        "event_id": ev.get("id"),
        "headline": ev.get("summary", ""),
        "time_start": start.strftime("%H:%M") if start else None,
        "time_end": end.strftime("%H:%M") if end else None,
        "untimed": start is None,
        "colour": colour.name if colour else "(default)",
        "colour_id": colour.google_color_id if colour else None,
        # enriched from the linked Job row (may be None for manually-created events)
        "customer": job.customer_name if job else None,
        "customer_phone": job.customer_phone if job else None,   # for the "on our way" text
        "address": job.address if job else None,
        "account_type": (job.account_type.value if (job and job.account_type) else None),
        "booking_lane": (job.booking_lane.value if job else None),
        "scope": (job.scope if job else None),
        "job_id": (str(job.id) if job else None),   # crew fetch reference photos by this
        # Manager's post-booking additions on the calendar event, surfaced to the crew:
        "manager_notes": manager_notes_from_desc(ev.get("description")),   # typed under NOTES: on Calendar
        "photos_link": ((job.details or {}).get("dropbox") or {}).get("link") if job else None,
    }


def build_day_board(events: list[dict], colour_by_id: dict[int, ColourMap],
                    jobs_by_event: dict[str, Job] | None = None) -> dict:
    jobs_by_event = jobs_by_event or {}
    trucks: dict[str, list] = {}
    status: dict[str, list] = {}
    unassigned: list = []
    notes_dropped = 0

    for ev in events:
        if is_manager_note(ev.get("summary", "")):   # §4 — first, before anything else
            notes_dropped += 1
            continue
        cid = ev.get("colorId")
        colour = colour_by_id.get(int(cid)) if cid else None
        job = _job_view(ev, colour, jobs_by_event.get(ev.get("id")))

        if colour is None or colour.kind == ColourKind.unassigned:
            unassigned.append(job)
        elif colour.kind == ColourKind.status:
            status.setdefault(colour.name, []).append(job)
        else:  # assignable -> a truck (if the colour is mapped) else the colour name
            key = f"Truck {colour.assigned_truck}" if colour.assigned_truck else f"{colour.name} (unmapped)"
            trucks.setdefault(key, []).append(job)

    for group in trucks.values():          # route order = list order (start-time/stack order)
        for i, job in enumerate(group, 1):
            job["stop"] = i

    return {
        "trucks": trucks,
        "status": status,
        "unassigned": unassigned,
        "notes_dropped": notes_dropped,
        "counts": {
            "trucks": {k: len(v) for k, v in trucks.items()},
            "status": {k: len(v) for k, v in status.items()},
            "unassigned": len(unassigned),
        },
    }


def read_day(db: DbSession, brand: Brand, on_date: date) -> dict:
    events = gcal.list_events_for_day(on_date)
    ids = [e["id"] for e in events if e.get("id")]
    jobs_by_event: dict[str, Job] = {}
    if ids:
        rows = db.scalars(
            select(Job).where(Job.brand == brand, Job.gcal_event_id.in_(ids))
        ).all()
        jobs_by_event = {j.gcal_event_id: j for j in rows}

    cmap = db.scalars(select(ColourMap).where(ColourMap.brand == brand)).all()
    colour_by_id = {r.google_color_id: r for r in cmap if r.google_color_id is not None}

    board = build_day_board(events, colour_by_id, jobs_by_event)
    board["date"] = on_date.isoformat()
    board["brand"] = brand.value
    return board
