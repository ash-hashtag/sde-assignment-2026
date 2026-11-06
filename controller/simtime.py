"""Simulated-time helpers. Minute 0 is D0 00:00 IST; history has negative minutes."""
from __future__ import annotations

import datetime as dt
from functools import lru_cache

MIN_PER_DAY = 1440


class Clock:
    def __init__(self, origin_iso_date: str):
        self.origin = dt.date.fromisoformat(origin_iso_date)

    @classmethod
    def from_state(cls, state: dict) -> "Clock":
        t = dt.datetime.fromisoformat(state["ts"]).replace(tzinfo=None)
        origin = t - dt.timedelta(minutes=state["sim_minute"])
        return cls(origin.date().isoformat())

    def minute(self, ts: str) -> int:
        """'2027-01-06T14:15:00+05:30' -> sim minute. Hot path in ingestion, hence the cached date part."""
        return self._day(ts[:10]) * MIN_PER_DAY + int(ts[11:13]) * 60 + int(ts[14:16])

    @lru_cache(maxsize=4096)
    def _day(self, date_s: str) -> int:
        return (dt.date.fromisoformat(date_s) - self.origin).days


def day_hour(minute: int) -> tuple[int, int]:
    d, m = divmod(minute, MIN_PER_DAY)
    return d, m // 60


def fmt(minute: int) -> str:
    """Human label in the scenario's own notation: 'D3 14:00' (history is 'D-2 09:15')."""
    d, m = divmod(minute, MIN_PER_DAY)
    return f"D{d} {m // 60:02d}:{m % 60:02d}"


def parse(label: str) -> int:
    day, hm = label.strip().split()
    h, m = hm.split(":")
    return int(day.lstrip("Dd")) * MIN_PER_DAY + int(h) * 60 + int(m)


def hour_index(minute: int) -> int:
    """Absolute hour number, used for sliding windows that cross midnight."""
    return minute // 60
