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


def _assert_punch_calendar(cal_id: str | None) -> str:
    """The off-board punch-time calendar is a third writable target. Hard-refuses the two
    live dispatch calendars + primary + the TEST + reminder calendars — punch events go
    ONLY to the configured punch calendar."""
    if not cal_id:
        raise CalendarGuardError("No punch calendar configured (google_punch_calendar_id).")
    if (cal_id in FORBIDDEN or cal_id == settings.google_test_calendar_id
            or cal_id == settings.google_reminder_calendar_id):
        raise CalendarGuardError(f"REFUSING: '{cal_id}' is not the punch calendar.")
    if cal_id != settings.google_punch_calendar_id:
        raise CalendarGuardError("REFUSING: target is not the configured punch calendar.")
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


# ── Punch-time calendar (off-board; mirrors crew clock in/out) ──────────────────

import re as _re


def parse_clock(s: str | None) -> time | None:
    """"7:30am" / "3:05 PM" / "15:05" -> time, or None. Matches the prototype's clock format."""
    if not s:
        return None
    m = _re.match(r"^\s*(\d{1,2}):(\d{2})\s*([ap])\.?m\.?\s*$", str(s), _re.I)
    if m:
        h, mn, ap = int(m.group(1)), int(m.group(2)), m.group(3).lower()
        if ap == "p" and h < 12:
            h += 12
        if ap == "a" and h == 12:
            h = 0
        return time(hour=h % 24, minute=mn) if 0 <= mn < 60 else None
    m = _re.match(r"^\s*(\d{1,2}):(\d{2})\s*$", str(s))   # 24h fallback
    if m and 0 <= int(m.group(1)) < 24 and 0 <= int(m.group(2)) < 60:
        return time(hour=int(m.group(1)), minute=int(m.group(2)))
    return None


def punch_calendar_accessible() -> bool:
    """True only if the service account can reach the punch calendar (shared with it).
    Lets the clock sync mirror best-effort and skip cleanly until it's shared."""
    cal = settings.google_punch_calendar_id
    if not cal or cal in FORBIDDEN or cal in (settings.google_test_calendar_id,
                                              settings.google_reminder_calendar_id):
        return False
    try:
        _svc().calendars().get(calendarId=cal).execute()
        return True
    except Exception:
        return False


def _punch_body(*, name: str, on_date: date, in_str: str | None, out_str: str | None,
                truck: str | None) -> dict:
    """One event per person per day. Timed in→out when both parse (a shift block); else an
    all-day marker. Truck rides in the title. Tagged so it's identifiable as app-created."""
    truck_suffix = f" · #{truck}" if truck else ""
    t_in, t_out = parse_clock(in_str), parse_clock(out_str)
    body: dict = {
        "extendedProperties": {"private": {"ij_app": "1", "ij_kind": "punch"}},
    }
    if t_in and t_out and t_out > t_in:
        body["summary"] = f"{name} · {in_str}–{out_str}{truck_suffix}"
        body["start"] = {"dateTime": datetime.combine(on_date, t_in).isoformat(), "timeZone": TZ}
        body["end"] = {"dateTime": datetime.combine(on_date, t_out).isoformat(), "timeZone": TZ}
    elif t_in:   # clocked in, not out yet (or out didn't parse) — a 30-min "on the clock" marker
        end_dt = datetime.combine(on_date, t_in) + timedelta(minutes=30)
        body["summary"] = f"{name} · in {in_str}{' (working)' if not out_str else ''}{truck_suffix}"
        body["start"] = {"dateTime": datetime.combine(on_date, t_in).isoformat(), "timeZone": TZ}
        body["end"] = {"dateTime": end_dt.isoformat(), "timeZone": TZ}
    else:        # no parseable time — all-day marker
        body["summary"] = f"{name}{truck_suffix}"
        body["start"] = {"date": on_date.isoformat()}
        body["end"] = {"date": (on_date + timedelta(days=1)).isoformat()}
    return body


def upsert_punch_event(*, event_id: str | None, name: str, on_date: date,
                       in_str: str | None, out_str: str | None, truck: str | None) -> str:
    """Create or update the one punch event for a person's day; returns its event id. Update
    in place (by id) as the punch evolves clock-in → clock-out."""
    cal = _assert_punch_calendar(settings.google_punch_calendar_id)
    body = _punch_body(name=name, on_date=on_date, in_str=in_str, out_str=out_str, truck=truck)
    if event_id:
        ev = _svc().events().patch(calendarId=cal, eventId=event_id, body=body).execute()
    else:
        ev = _svc().events().insert(calendarId=cal, body=body).execute()
    return ev["id"]


def delete_punch_event(event_id: str) -> None:
    cal = _assert_punch_calendar(settings.google_punch_calendar_id)
    _svc().events().delete(calendarId=cal, eventId=event_id).execute()
