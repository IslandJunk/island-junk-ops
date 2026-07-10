"""Google Calendar client — the app's ONLY calendar writer, and it writes to the
TEST calendar exclusively. The two live calendar IDs (CLAUDE.md §2) are hard-coded
as forbidden; every read/write asserts the target is exactly the configured TEST
calendar before doing anything. This is the same guard proven in /spike.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from google.oauth2 import service_account
from googleapiclient.discovery import build

from app.core.config import settings

_TZINFO = ZoneInfo("America/Vancouver")

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TZ = "America/Vancouver"

# NEVER write here (CLAUDE.md §2).
LIVE_VICTORIA = "c_f35b41c1bf665fba2fef6fd34c0581a41c682867550cb30abf7228051622d987@group.calendar.google.com"
LIVE_JOBS2 = "c_77fcdcaa4570ff7ea0bf898fbd6153deed641acb49381380375c6555f6e9820e@group.calendar.google.com"
FORBIDDEN = {LIVE_VICTORIA, LIVE_JOBS2, "primary"}

_service = None


class CalendarGuardError(RuntimeError):
    pass


def _assert_test_calendar(cal_id: str | None) -> str:
    if not cal_id:
        raise CalendarGuardError("No TEST calendar configured (google_test_calendar_id).")
    if cal_id in FORBIDDEN:
        raise CalendarGuardError(f"REFUSING: '{cal_id}' is a live/forbidden calendar.")
    if cal_id != settings.google_test_calendar_id:
        raise CalendarGuardError("REFUSING: target is not the configured TEST calendar.")
    return cal_id


def _assert_reminder_calendar(cal_id: str | None) -> str:
    """The off-board CC-charge reminder calendar (§9/§11) is the ONLY other writable
    target. Still hard-refuses the two live dispatch calendars + primary + the TEST cal."""
    if not cal_id:
        raise CalendarGuardError("No reminder calendar configured (google_reminder_calendar_id).")
    if cal_id in FORBIDDEN or cal_id == settings.google_test_calendar_id:
        raise CalendarGuardError(f"REFUSING: '{cal_id}' is not the reminder calendar.")
    if cal_id != settings.google_reminder_calendar_id:
        raise CalendarGuardError("REFUSING: target is not the configured reminder calendar.")
    return cal_id


# CC-charge reminder event colours (Google colorIds; mirror the app lifecycle):
CC_UNPAID_COLOR = 4   # Flamingo — residential unpaid (matches the day-board lifecycle)
CC_PAID_COLOR = 3     # Grape/purple — paid / complete (Wes: "turned purple for complete")


def _svc():
    global _service
    if _service is None:
        creds = service_account.Credentials.from_service_account_file(
            settings.google_service_account_file, scopes=SCOPES
        )
        _service = build("calendar", "v3", credentials=creds, cache_discovery=False)
    return _service


def create_event(
    *, summary: str, description: str, color_id: str | int,
    on_date: date, start_time: time | None = None, end_time: time | None = None,
) -> str:
    """Create ONE event on the TEST calendar; returns its event id.

    Slot time is positional/fake (the manager stacks later) — the real time lives in
    the headline. We still create a *timed* event (never all-day) so it stacks, per
    the spike. Defaults to the 7:30am workday start when no time is given.
    """
    cal = _assert_test_calendar(settings.google_test_calendar_id)
    start_dt = datetime.combine(on_date, start_time or time(7, 30))
    end_dt = datetime.combine(on_date, end_time) if end_time else start_dt + timedelta(minutes=30)
    body = {
        "summary": summary,
        "description": description,
        "colorId": str(color_id),
        "start": {"dateTime": start_dt.isoformat(), "timeZone": TZ},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": TZ},
        "extendedProperties": {"private": {"ij_app": "1"}},  # tag app-created events
    }
    ev = _svc().events().insert(calendarId=cal, body=body).execute()
    return ev["id"]


def list_events_for_day(on_date: date) -> list[dict]:
    """Read one local day's events from the TEST calendar, ordered by start time.

    `orderBy=startTime` is the mechanism the spike proved for recovering the manager's
    manual top-to-bottom stack order (the vertical position = the start time). The
    caller then drops `#` notes and groups by colour.
    """
    cal = _assert_test_calendar(settings.google_test_calendar_id)
    start = datetime.combine(on_date, time(0, 0), tzinfo=_TZINFO)
    end = start + timedelta(days=1)
    items, page_token = [], None
    while True:
        resp = _svc().events().list(
            calendarId=cal, singleEvents=True, orderBy="startTime",
            timeMin=start.isoformat(), timeMax=end.isoformat(),
            maxResults=2500, pageToken=page_token,
        ).execute()
        items.extend(resp.get("items", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return items


def get_event(event_id: str) -> dict:
    cal = _assert_test_calendar(settings.google_test_calendar_id)
    return _svc().events().get(calendarId=cal, eventId=event_id).execute()


def delete_event(event_id: str) -> None:
    cal = _assert_test_calendar(settings.google_test_calendar_id)
    _svc().events().delete(calendarId=cal, eventId=event_id).execute()


# ── CC-charge reminder calendar (off-board; §9/§11) ────────────────────────────

def reminder_calendar_accessible() -> bool:
    """True only if the service account can reach the reminder calendar (shared with it).
    Lets callers mirror best-effort and skip cleanly until Wes shares the calendar."""
    cal = settings.google_reminder_calendar_id
    if not cal or cal in FORBIDDEN or cal == settings.google_test_calendar_id:
        return False
    try:
        _svc().calendars().get(calendarId=cal).execute()
        return True
    except Exception:
        return False


def create_reminder_event(*, summary: str, description: str, on_date: date,
                          color_id: str | int = CC_UNPAID_COLOR) -> str:
    """Create an ALL-DAY CC-charge reminder on the reminder calendar (on the due date).
    Returns the event id. Tagged so it's identifiable as app-created."""
    cal = _assert_reminder_calendar(settings.google_reminder_calendar_id)
    body = {
        "summary": summary,
        "description": description,
        "colorId": str(color_id),
        "start": {"date": on_date.isoformat()},
        "end": {"date": (on_date + timedelta(days=1)).isoformat()},
        "extendedProperties": {"private": {"ij_app": "1", "ij_kind": "cc_charge"}},
    }
    ev = _svc().events().insert(calendarId=cal, body=body).execute()
    return ev["id"]


def recolor_reminder_event(event_id: str, color_id: str | int) -> None:
    """Recolour a reminder event (e.g. -> purple/Grape when the customer pays)."""
    cal = _assert_reminder_calendar(settings.google_reminder_calendar_id)
    _svc().events().patch(calendarId=cal, eventId=event_id, body={"colorId": str(color_id)}).execute()


def delete_reminder_event(event_id: str) -> None:
    cal = _assert_reminder_calendar(settings.google_reminder_calendar_id)
    _svc().events().delete(calendarId=cal, eventId=event_id).execute()
