"""WS2 — auto-paint the dispatch calendar with lifecycle status colours.

The app writes to the calendar at booking; WS2 adds ONE more kind of write: when the crew
completes a job, paint its event the status colour so the manager's board reflects reality
without anyone hand-colouring it. Scope is deliberately narrow:

  * Only **crew-completion** colours are auto-painted — done -> Basil (green),
    awaiting_payment -> Tomato (red). The owner's close-out colours (unpaid -> Flamingo,
    invoiced -> Grape/purple) are set BY HAND and are never auto-painted (so the app can't
    stomp the owner's manual Flamingo/purple).
  * Writes go ONLY to the app's dedicated calendar (the TEST calendar now; the go-live crew
    calendar later). `gcal.recolor_event` -> `_assert_test_calendar` makes touching a live
    calendar physically impossible (CLAUDE.md §2).
  * The assigned truck is stored separately on the Job, so repainting to a status colour never
    loses "which truck did this" (§6).

Colour ids are the classic Google palette (matches the CC-charge constants in gcal.py). If the
editable colour map (ColourMap) later needs to drive these, source them from there — kept direct
here for the foundation.
"""
from __future__ import annotations

from sqlalchemy.orm import Session as DbSession

from app.integrations import gcal
from app.models.enums import JobStatus
from app.models.job import Job

# JobStatus -> Google colorId. CREW-completion colours ONLY.
CREW_STATUS_COLOR: dict[JobStatus, int] = {
    JobStatus.done: 10,              # Basil / green — done, paid on site / commercial complete
    JobStatus.awaiting_payment: 11,  # Tomato / red — awaiting e-transfer / bin dropped or returned
}


def paint_job_status(db: DbSession, job: Job) -> dict:
    """Best-effort paint of a job's calendar event to its crew-completion status colour.
    No-op (never raises) unless the job has a linked event AND its status is a crew-completion
    colour — so it can't touch the owner's manual close-out colours. Returns a small result dict
    for logging/tests. A calendar-guard breach is the one thing that still raises (it must)."""
    color = CREW_STATUS_COLOR.get(job.status)
    if color is None:
        return {"painted": False, "reason": "not_a_crew_status", "status": job.status.value}
    if not job.gcal_event_id:
        return {"painted": False, "reason": "no_event"}
    try:
        gcal.recolor_event(job.gcal_event_id, color)
        return {"painted": True, "color_id": color, "status": job.status.value}
    except gcal.CalendarGuardError:
        raise
    except Exception as e:  # a transient Google error must never break the crew's save
        return {"painted": False, "reason": f"gcal_error: {str(e)[:80]}"}
