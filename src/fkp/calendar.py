"""German public holidays, business days and quiet hours for outgoing messages."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from functools import lru_cache
from zoneinfo import ZoneInfo

from . import config


def easter(year: int) -> date:
    """Anonymous Gregorian algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month, day = divmod(h + l_ - 7 * m + 114, 31)
    return date(year, month, day + 1)


# State holidays on top of the national ones (the most common; extend as needed)
_STATE: dict[str, list[str]] = {
    "BE": ["03-08"],
    "BB": ["10-31"],
    "BW": ["01-06", "corpus_christi", "11-01"],
    "BY": ["01-06", "corpus_christi", "08-15", "11-01"],
    "HE": ["corpus_christi"],
    "HH": ["10-31"],
    "MV": ["03-08", "10-31"],
    "NI": ["10-31"],
    "NW": ["corpus_christi", "11-01"],
    "RP": ["corpus_christi", "11-01"],
    "SL": ["corpus_christi", "08-15", "11-01"],
    "SN": ["10-31"],
    "ST": ["01-06", "10-31"],
    "SH": ["10-31"],
    "TH": ["09-20", "10-31"],
    "HB": ["10-31"],
}


@lru_cache(maxsize=64)
def holidays(year: int, state: str = "") -> frozenset[date]:
    e = easter(year)
    days = {
        date(year, 1, 1), e - timedelta(days=2), e + timedelta(days=1), date(year, 5, 1), e + timedelta(days=39),
        e + timedelta(days=50), date(year, 10, 3), date(year, 12, 25), date(year, 12, 26),
    }
    for d in _STATE.get(state, []):
        days.add(e + timedelta(days=60) if d == "corpus_christi" else date(year, int(d[:2]), int(d[3:])))
    return frozenset(days)


def tz() -> ZoneInfo:
    return ZoneInfo(config.settings()["timezone"])


def is_business_day(d: date, state: str | None = None) -> bool:
    st = state if state is not None else config.settings()["followups"]["state"]
    return d.weekday() < 5 and d not in holidays(d.year, st)


def add_business_days(d: date, n: int) -> date:
    out = d
    while n > 0:
        out += timedelta(days=1)
        if is_business_day(out):
            n -= 1
    return out


def next_send_slot(at: datetime) -> datetime:
    """The first moment at or after `at` outside quiet hours, Sundays and public holidays."""
    f = config.settings()["followups"]
    zone = tz()
    local = at.astimezone(zone)
    start = time.fromisoformat(f["quiet_hours"]["start"])
    end = time.fromisoformat(f["quiet_hours"]["end"])
    for _ in range(14):
        d = local.date()
        blocked_day = (f.get("no_sundays") and d.weekday() == 6) or (f.get("no_public_holidays") and d in holidays(d.year, f["state"]))
        if blocked_day:
            local = datetime.combine(d + timedelta(days=1), end, zone)
            continue
        t = local.timetz().replace(tzinfo=None)
        if t >= start:
            local = datetime.combine(d + timedelta(days=1), end, zone)
            continue
        if t < end:
            local = datetime.combine(d, end, zone)
            continue
        return local.astimezone(at.tzinfo)
    raise RuntimeError("no send slot within two weeks")
