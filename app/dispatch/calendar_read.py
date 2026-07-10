"""Calendar-reader helpers: the `#` note filter and the headline time parser.

Rules that must be applied FIRST when reading events. The Day Board reader
(app/dispatch/day_board.py) drops manager notes (`is_manager_note`) before any
colour-filter / stack-order / time logic, and reads the time from the HEADLINE
(never the calendar slot) via `parse_headline_time`.
"""
from __future__ import annotations

import re
from datetime import time


def is_manager_note(title: str | None) -> bool:
    """The `#` rule (scheduling spec §4).

    A calendar entry whose title's FIRST non-whitespace character is `#` is a
    manager-only note, not a job — the app ignores it entirely (never a job, never in
    a truck's colour filter, never a route-order slot, never time-parsed, never in any
    crew view / "on our way" / ETA text) and never edits it.

    Only a LEADING `#` counts: `Load #42` and `Truck #3` (# not leading) are normal
    jobs. Leading whitespace is trimmed first so a stray space can't defeat the rule.
    Colour and position are irrelevant — the title decides.
    """
    if not title:
        return False
    return title.lstrip().startswith("#")


# " · " or " - " — the separators buildHeadline uses between time and the rest.
_SEP = re.compile(r"\s+[·\-]\s+")
# The whole first segment must be a time: digits, optional -range, optional am/pm (ignored).
_TIME = re.compile(r"^(\d{1,4})(?:\s*-\s*(\d{1,4}))?\s*(?:[ap]m)?$", re.IGNORECASE)


def _clock(token: str) -> time | None:
    """A headline clock token -> time, fixed workday 7:30am-3:30pm, no am/pm.
    `8`->08:00, `830`->08:30, `1230`->12:30. Hours 1-6 are afternoon (+12): `1`->13:00."""
    d = token.strip()
    if not d.isdigit():
        return None
    if len(d) <= 2:
        h, m = int(d), 0
    elif len(d) == 3:
        h, m = int(d[0]), int(d[1:])
    elif len(d) == 4:
        h, m = int(d[0:2]), int(d[2:])
    else:
        return None
    if 1 <= h <= 6:          # fixed-day rule: never crosses noon (1-3 = 1-3pm)
        h += 12
    if h > 23 or m > 59:
        return None
    return time(h, m)


def parse_headline_time(headline: str | None) -> tuple[time | None, time | None]:
    """Read the job time from the HEADLINE (spec §3a). Returns (start, end):
    a single time -> (start, None); a range -> (start, end); no time -> (None, None).
    Only the first `·`/`-`-delimited segment is considered, and it must be a pure time
    pattern — so `Load #42`, `Yard pickup - bin 20-04`, `123 Main St` stay untimed.
    """
    if not headline:
        return (None, None)
    first = _SEP.split(headline.strip(), 1)[0].strip()
    m = _TIME.match(first)
    if not m:
        return (None, None)
    start = _clock(m.group(1))
    if start is None:
        return (None, None)
    end = _clock(m.group(2)) if m.group(2) else None
    return (start, end)
