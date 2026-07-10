#!/usr/bin/env python3
"""
Island Junk — Stack-Order Spike
================================
GOAL: Prove we can reliably recover the manager's MANUAL top-to-bottom stacking
order of Google Calendar events via the API — the highest-risk unknown in the
dispatch build (CLAUDE.md §6, scheduling spec §2).

THE HYPOTHESIS BEING TESTED
---------------------------
In Google Calendar's day/week grid, an event's VERTICAL position is a function
of its slot start time. When the manager drags a job "under" another to set route
order, the only thing that physically persists is that event's start/end time —
the Calendar API has no separate "position" / "z-order" field (the event resource
exposes only start, end, created, updated, colorId, summary, ...). Therefore:

    reading events with orderBy="startTime" should return them in the EXACT
    top-to-bottom order the manager stacked them.

Note the two DIFFERENT uses of the slot time, which the spec keeps separate:
  * slot time as the JOB'S REAL TIME      -> ignored (real time is in the headline)
  * slot time as the VERTICAL STACK ORDER -> THIS is what we read to get route order

The only place this can break is EXACT start-time ties (two events dragged onto
the identical slot). This script proves the clean case and characterises the tie
case, then recommends the mitigation.

SAFETY
------
This script refuses to talk to anything but the known TEST calendar. The two live
calendar IDs (CLAUDE.md §2) are hard-coded as forbidden and the run aborts if the
target is not exactly the TEST id. Reads AND writes are guarded.

USAGE
-----
    python stack_order_spike.py all       # cleanup -> seed -> read -> verify (default)
    python stack_order_spike.py cleanup    # delete only this spike's events on TEST
    python stack_order_spike.py seed       # create the test events on TEST
    python stack_order_spike.py read       # read back + print the order (no writes)
    python stack_order_spike.py verify     # read + judge PASS/FAIL (no writes)
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ─────────────────────────────────────────────────────────────────────────────
# SAFETY GUARD — the whole point of the spike is to never touch a live calendar.
# ─────────────────────────────────────────────────────────────────────────────
TEST_CALENDAR_ID = "c_37fdece0f833b792c645b6d195f07c865611cd9de35a2a142620b768e6324f34@group.calendar.google.com"

LIVE_VICTORIA = "c_f35b41c1bf665fba2fef6fd34c0581a41c682867550cb30abf7228051622d987@group.calendar.google.com"
LIVE_JOBS2    = "c_77fcdcaa4570ff7ea0bf898fbd6153deed641acb49381380375c6555f6e9820e@group.calendar.google.com"
FORBIDDEN     = {LIVE_VICTORIA, LIVE_JOBS2, "primary"}


def assert_safe_target(cal_id: str) -> None:
    """Abort unless the target is EXACTLY the known TEST calendar."""
    if cal_id in FORBIDDEN:
        sys.exit(f"\n*** REFUSING TO RUN: '{cal_id}' is a LIVE / forbidden calendar. ***\n")
    if cal_id != TEST_CALENDAR_ID:
        sys.exit(
            "\n*** REFUSING TO RUN: target is not the known TEST calendar. ***\n"
            f"    target: {cal_id}\n    expected TEST: {TEST_CALENDAR_ID}\n"
        )


SCOPES = ["https://www.googleapis.com/auth/calendar"]
HERE = Path(__file__).resolve().parent
KEY_PATH = HERE / "service-account-key.json"
OUT_DIR = HERE / "out"

# A marker so we can find + delete ONLY our events, and a safely-future test day.
SPIKE_TAG = "1"
TEST_DATE = "2026-09-15"          # far-future, keeps TEST board uncluttered
TZ = "America/Vancouver"          # Island Junk is in BC

# ─────────────────────────────────────────────────────────────────────────────
# TEST DATA
# Each row = one event in the INTENDED top-to-bottom stack order (stack_index).
# We give increasing start times to simulate exactly what a UI drag persists.
# We deliberately CREATE them shuffled (create_order) so a PASS can't be an
# accident of "the API just echoed creation order".
#
# colorId: classic Google palette (1-11). Colour is irrelevant to ordering — we
# include same-colour pairs only to prove that.
#
#  idx  time(local) colorId  block   headline                              why it's here
# ─────────────────────────────────────────────────────────────────────────────
MAIN_STACK = [
    # stack_index, start "HH:MM:SS", colorId, headline
    (0, "03:00:00",  6, "8 - Smith, 123 Oak (1/4 load)"),      # timed headline
    (1, "03:15:00",  9, "830 - Lee, 45 Fern (bin drop)"),      # shares colour 9 w/ idx2
    (2, "03:30:00",  9, "Yard pickup - bin 20-04"),            # UNTIMED headline, colour 9
    (3, "03:45:00",  6, "10 - Nguyen, 9 Elm (1/2 load)"),      # shares colour 6 w/ idx0
    (4, "04:00:00",  5, "1230-2 - Park, 88 Bay (window)"),     # timed RANGE headline
    (5, "04:15:00",  5, "Property sweep - Rockland"),          # UNTIMED, shares colour 5 w/ idx4
]

# The pathological case: three events at the EXACT same start time + full overlap.
# In the UI these render side-by-side (columns), not a clean vertical stack — and
# that is itself the signal that a true tie exists. We probe what the API returns.
TIE_BLOCK = [
    (100, "05:00:00", 11, "TIE-A - stacked first"),
    (101, "05:00:00", 11, "TIE-B - stacked second"),
    (102, "05:00:00", 11, "TIE-C - stacked third"),
]

# Create in a shuffled order so recovery can't be creation-order coincidence.
CREATE_ORDER = [3, 0, 5, 101, 2, 100, 4, 1, 102]  # by stack_index / tie idx


def _svc():
    if not KEY_PATH.exists():
        sys.exit(f"Service-account key not found at {KEY_PATH}")
    creds = service_account.Credentials.from_service_account_file(str(KEY_PATH), scopes=SCOPES)
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


def _all_rows_by_index():
    rows = {}
    for idx, t, color, summary in MAIN_STACK:
        rows[idx] = ("main", idx, t, color, summary)
    for idx, t, color, summary in TIE_BLOCK:
        rows[idx] = ("tie", idx, t, color, summary)
    return rows


def _end_time(start_hhmmss: str) -> str:
    """+10 minutes; keeps non-tie events from overlapping (so they stack, not column)."""
    h, m, s = (int(x) for x in start_hhmmss.split(":"))
    total = h * 3600 + m * 60 + s + 10 * 60
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:{total % 60:02d}"


# ── Display helpers (used by the `read` explorer) ────────────────────────────
COLOR_NAMES = {
    "1": "Lavender", "2": "Sage", "3": "Grape", "4": "Flamingo", "5": "Banana",
    "6": "Tangerine", "7": "Peacock", "8": "Graphite", "9": "Blueberry",
    "10": "Basil", "11": "Tomato",
}

def _start_raw(ev):
    s = ev["start"]
    return s.get("dateTime", s.get("date", "?"))

def _local_date(ev):
    return _start_raw(ev)[0:10]

def _local_time(ev):
    s = _start_raw(ev)
    return s[11:19] if "T" in s else "(all-day)"

def _is_all_day(ev):
    return "T" not in _start_raw(ev)

def _color_name(ev):
    cid = ev.get("colorId")
    return COLOR_NAMES.get(cid, "(default)") if cid else "(default)"


# ─────────────────────────────────────────────────────────────────────────────
# OPERATIONS
# ─────────────────────────────────────────────────────────────────────────────
def op_cleanup(svc, verbose=True):
    """Delete ONLY events this spike created (matched by our private tag)."""
    assert_safe_target(TEST_CALENDAR_ID)
    deleted = 0
    page_token = None
    while True:
        resp = svc.events().list(
            calendarId=TEST_CALENDAR_ID,
            privateExtendedProperty=f"ij_spike={SPIKE_TAG}",
            singleEvents=True,
            maxResults=2500,
            pageToken=page_token,
        ).execute()
        for ev in resp.get("items", []):
            svc.events().delete(calendarId=TEST_CALENDAR_ID, eventId=ev["id"]).execute()
            deleted += 1
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    if verbose:
        print(f"[cleanup] deleted {deleted} prior spike event(s) from TEST calendar.")
    return deleted


def op_seed(svc):
    """Create the test events on the TEST calendar in a shuffled create order."""
    assert_safe_target(TEST_CALENDAR_ID)
    rows = _all_rows_by_index()
    created = []
    for order_pos, idx in enumerate(CREATE_ORDER):
        block, stack_index, start_t, color, summary = rows[idx]
        body = {
            "summary": summary,
            "colorId": str(color),
            "start": {"dateTime": f"{TEST_DATE}T{start_t}", "timeZone": TZ},
            "end":   {"dateTime": f"{TEST_DATE}T{_end_time(start_t)}", "timeZone": TZ},
            "extendedProperties": {
                "private": {
                    "ij_spike": SPIKE_TAG,
                    "block": block,
                    "stack_index": str(stack_index),
                    "create_pos": str(order_pos),
                }
            },
        }
        ev = svc.events().insert(calendarId=TEST_CALENDAR_ID, body=body).execute()
        created.append((order_pos, stack_index, start_t, summary, ev["id"]))
        print(f"[seed] create#{order_pos}  stack_index={stack_index:>3}  {start_t}  {summary}")
    print(f"[seed] created {len(created)} events on TEST calendar.")
    return created


def _read_events(svc):
    """Read spike events with orderBy=startTime (the mechanism under test).

    Wide time window on purpose: you can drag events to ANY day in the TEST
    calendar and this still finds them, then groups them per day on display.
    """
    assert_safe_target(TEST_CALENDAR_ID)
    items, page_token = [], None
    while True:
        resp = svc.events().list(
            calendarId=TEST_CALENDAR_ID,
            privateExtendedProperty=f"ij_spike={SPIKE_TAG}",
            singleEvents=True,          # required for orderBy=startTime
            orderBy="startTime",        # <-- THE HYPOTHESIS
            timeMin="2024-01-01T00:00:00Z",
            timeMax="2030-01-01T00:00:00Z",
            maxResults=2500,
            pageToken=page_token,
        ).execute()
        items.extend(resp.get("items", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return items


def _meta(ev):
    p = ev.get("extendedProperties", {}).get("private", {})
    return p.get("block"), int(p.get("stack_index", -1)), int(p.get("create_pos", -1))


def op_read(svc):
    """Explorer view: read back whatever is on the TEST calendar now, grouped by
    day, in recovered top-to-bottom route order. Use this after you drag / stretch
    / move events by hand in the UI."""
    from collections import OrderedDict
    items = _read_events(svc)
    if not items:
        print("[read] no spike events found. Seed first: stack_order_spike.py seed")
        return items

    days = OrderedDict()
    for ev in items:                      # items already in start-time order
        days.setdefault(_local_date(ev), []).append(ev)

    print(f"\n[read] {len(items)} spike event(s) across {len(days)} day(s), "
          f"recovered by orderBy=startTime:\n")

    for day, evs in days.items():
        print(f"  == {day}  ({len(evs)} events) -- route order, top-to-bottom ==")
        seen = {}
        for pos, ev in enumerate(evs, 1):
            t = _local_time(ev)
            if not _is_all_day(ev):
                seen[(_color_name(ev), t)] = seen.get((_color_name(ev), t), 0) + 1
            flag = "   <-- ALL-DAY: won't hold a stack slot!" if _is_all_day(ev) else ""
            print(f"     {pos:>2}. {t:<9} [{_color_name(ev):<9}] {ev.get('summary','')}{flag}")
        # A tie only bites WITHIN one truck: same colour AND same exact time.
        # A same-time collision across different colours is harmless (separate routes).
        real_ties = [(c, t) for (c, t), n in seen.items() if n > 1]
        if real_ties:
            for cname, t in real_ties:
                print(f"     [!] SAME-TRUCK tie: colour '{cname}' has >1 event at {t} -> "
                      f"order between them isn't meaningful; nudge one to break it.")
        # per-truck (colour) slice = exactly how a truck's day is built
        by_color = OrderedDict()
        for ev in evs:
            by_color.setdefault(_color_name(ev), []).append(ev.get("summary", ""))
        print("     per truck (colour = truck):")
        for cname, names in by_color.items():
            print(f"        {cname:<9}: {', '.join(names)}")
        print()
    return items


def op_verify(svc):
    """Automated seed-check: only meaningful on the freshly-seeded arrangement.
    After you hand-drag events, use `read` instead (intended order no longer applies)."""
    items = _read_events(svc)
    print(f"\n[verify] {len(items)} spike events by orderBy=startTime:")
    print(f"  {'API#':>4}  {'stack_idx':>9}  {'create#':>7}  {'block':<5}  {'start(local)':<13}  headline")
    print("  " + "-" * 88)
    for api_pos, ev in enumerate(items):
        block, sidx, cpos = _meta(ev)
        print(f"  {api_pos:>4}  {sidx:>9}  {cpos:>7}  {block:<5}  {_local_time(ev):<13}  {ev.get('summary','')}")

    main = [ev for ev in items if _meta(ev)[0] == "main"]
    tie  = [ev for ev in items if _meta(ev)[0] == "tie"]

    print("\n" + "=" * 78)
    print("VERDICT")
    print("=" * 78)

    # --- Main stack: does API order == intended stack order (0..5)? ---
    api_order      = [_meta(ev)[1] for ev in main]
    intended_order = sorted(api_order)
    create_order   = [_meta(ev)[2] for ev in main]  # to prove it's NOT creation order
    main_pass = (api_order == intended_order)

    print(f"\nMAIN STACK ({len(main)} events, distinct start times):")
    print(f"  intended top->bottom : {intended_order}")
    print(f"  API returned         : {api_order}")
    print(f"  (their create order  : {create_order}  <- deliberately shuffled)")
    print(f"  RESULT: {'PASS  exact stack order recovered' if main_pass else 'FAIL  order NOT recovered'}")

    # --- Tie block: stability + what the tie order correlates with ---
    tie_order = [_meta(ev)[1] for ev in tie]
    print(f"\nTIE BLOCK ({len(tie)} events, IDENTICAL start time):")
    print(f"  API returned stack_index order: {tie_order}")

    # re-read twice more to check the tie order is at least STABLE across reads
    stable = True
    first = tie_order
    for _ in range(2):
        again = [_meta(ev)[1] for ev in _read_events(svc) if _meta(ev)[0] == "tie"]
        if again != first:
            stable = False
    print(f"  stable across 3 reads: {'YES (deterministic)' if stable else 'NO (non-deterministic!)'}")
    print("  note: true ties render SIDE-BY-SIDE in the UI, not vertically stacked —")
    print("        so a real vertical stack never produces an exact tie by construction.")

    # --- Overall ---
    print("\n" + "-" * 78)
    if main_pass:
        print("STACK-ORDER CAPTURE: PROVEN for the real case (distinct start times).")
        print("Mitigation for the tie edge-case: ensure distinct start times (see README).")
    else:
        print("STACK-ORDER CAPTURE: NOT proven — investigate before building dispatch.")
    print("-" * 78)

    OUT_DIR.mkdir(exist_ok=True)
    report = {
        "main_pass": main_pass,
        "main_intended": intended_order,
        "main_api": api_order,
        "main_create_order": create_order,
        "tie_api_order": tie_order,
        "tie_stable": stable,
    }
    (OUT_DIR / "verdict.json").write_text(json.dumps(report, indent=2))
    print(f"\nWrote {OUT_DIR / 'verdict.json'}")
    return main_pass


def main():
    ap = argparse.ArgumentParser(description="Island Junk stack-order spike (TEST calendar only).")
    ap.add_argument("action", nargs="?", default="all",
                    choices=["all", "cleanup", "seed", "read", "verify"])
    args = ap.parse_args()

    print(f"Target calendar (TEST only): {TEST_CALENDAR_ID}")
    assert_safe_target(TEST_CALENDAR_ID)
    svc = _svc()

    if args.action == "cleanup":
        op_cleanup(svc)
    elif args.action == "seed":
        op_seed(svc)
    elif args.action == "read":
        op_read(svc)
    elif args.action == "verify":
        op_verify(svc)
    else:  # all
        op_cleanup(svc)
        op_seed(svc)
        print("\n[all] waiting briefly for calendar to index new events...")
        time.sleep(3)
        op_verify(svc)


if __name__ == "__main__":
    main()
