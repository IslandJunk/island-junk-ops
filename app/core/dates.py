"""Date helpers — BC statutory holidays + business-day arithmetic.

Used by the §9/§11 CC-charge reminder ("48 hours = 2 working days", per Wes — a Friday
drop lands on Tuesday), and reusable for the bin billable-day rule (weekends + BC stat
holidays are free). Holidays follow the BC observed set; the rate sheet also treats
Boxing Day and the National Day for Truth & Reconciliation as non-working, so both are
included here.
"""
from __future__ import annotations

from datetime import date, timedelta
from functools import lru_cache


def easter(year: int) -> date:
    """Gregorian Easter Sunday (Anonymous/Meeus computus)."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ell = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ell) // 451
    month = (h + ell - 7 * m + 114) // 31
    day = ((h + ell - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The nth `weekday` (Mon=0) of a month, e.g. 3rd Monday of February."""
    first = date(year, month, 1)
    offset = (weekday - first.weekday()) % 7
    return first + timedelta(days=offset + 7 * (n - 1))


def _monday_before(year: int, month: int, day: int) -> date:
    """The Monday on or before a given date (Victoria Day = Monday before May 25)."""
    d = date(year, month, day)
    return d - timedelta(days=(d.weekday()))


@lru_cache(maxsize=64)
def bc_stat_holidays(year: int) -> frozenset[date]:
    """BC statutory (observed) holidays for a year, plus Boxing Day and the National Day
    for Truth & Reconciliation (treated as non-working in Island Junk's calendar)."""
    return frozenset({
        date(year, 1, 1),                        # New Year's Day
        _nth_weekday(year, 2, 0, 3),             # Family Day (3rd Monday of February)
        easter(year) - timedelta(days=2),        # Good Friday
        _monday_before(year, 5, 24),             # Victoria Day (Monday before May 25)
        date(year, 7, 1),                        # Canada Day
        _nth_weekday(year, 8, 0, 1),             # BC Day (1st Monday of August)
        _nth_weekday(year, 9, 0, 1),             # Labour Day (1st Monday of September)
        date(year, 9, 30),                       # National Day for Truth & Reconciliation
        _nth_weekday(year, 10, 0, 2),            # Thanksgiving (2nd Monday of October)
        date(year, 11, 11),                      # Remembrance Day
        date(year, 12, 25),                      # Christmas Day
        date(year, 12, 26),                      # Boxing Day
    })


def is_working_day(d: date) -> bool:
    return d.weekday() < 5 and d not in bc_stat_holidays(d.year)


def add_business_days(start: date, n: int) -> date:
    """`start` + `n` working days, skipping weekends and BC stat holidays.
    n=2 from a Friday returns the following Tuesday."""
    d = start
    remaining = n
    while remaining > 0:
        d += timedelta(days=1)
        if is_working_day(d):
            remaining -= 1
    return d
