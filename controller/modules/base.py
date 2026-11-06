"""Shared helpers for policy modules."""
from __future__ import annotations

import math

from ..ctx import WorkflowCtx
from ..simtime import MIN_PER_DAY
from ..store import Store


class Module:
    name = "base"

    def __init__(self, store: Store, client):
        self.s, self.c = store, client

    def on_event(self, ev: dict):
        pass

    def intents(self, ctx: WorkflowCtx, **kw) -> list:
        return []

    # -- persistence for module state, one JSON blob per workflow
    def load(self, wf: str, default=None):
        return self.s.state_get(self.name, wf, default if default is not None else {})

    def save(self, wf: str, value):
        self.s.state_set(self.name, wf, value)


def daily_volume(ctx: WorkflowCtx, days: int = 3) -> dict:
    """Recent per-day dials / connected / engaged, from whatever data exists (history counts)."""
    d0 = ctx.day - days
    dials, conn = ctx.store.q("SELECT COALESCE(SUM(dials),0), COALESCE(SUM(conn),0) FROM agg_pick "
                              "WHERE wf=? AND day>=? AND day<?", (ctx.wf, d0, ctx.day))[0]
    c2, eng = ctx.store.q("SELECT COALESCE(SUM(conn),0), COALESCE(SUM(eng),0) FROM agg_eng "
                          "WHERE wf=? AND day>=? AND day<?", (ctx.wf, d0, ctx.day))[0]
    n_days = max(1, ctx.store.q1("SELECT COUNT(DISTINCT day) FROM agg_pick WHERE wf=? AND day>=? AND day<?",
                                 (ctx.wf, d0, ctx.day)) or 1)
    return {"dials_per_day": dials / n_days, "conn_per_day": conn / n_days,
            "pickup": conn / dials if dials else 0.0, "engagement": eng / c2 if c2 else 0.0}


def impact_score(ctx: WorkflowCtx, extra_conclusions_per_day: float) -> float:
    """Expected extra concluded leads per day, mapped to [0,1].

    1 - exp(-x / k) with k = 2% of the daily batch: a change worth 2% of a day's leads scores 0.63, 5% scores
    0.92. Negative or zero expected value scores 0. The same scale applies to every workflow, so a supervisor's
    queue ranked by it is ranked by expected conclusions relative to the size of the workflow.
    """
    k = 0.02 * max(1, ctx.spec["daily_batch"]["size"])
    return round(1 - math.exp(-max(0.0, extra_conclusions_per_day) / k), 3)


def window_bounds(ctx: WorkflowCtx, hours: int) -> list[tuple[int, int]]:
    return ctx.hour_keys(hours)


def keys_sql(keys: list[tuple[int, int]]) -> tuple[str, list]:
    """SQL fragment selecting rows whose (day, hour) is in keys."""
    if not keys:
        return "0", []
    return " OR ".join(["(day=? AND hour=?)"] * len(keys)), [x for k in keys for x in k]


def minute_to_dh(minute: int) -> tuple[int, int]:
    d, m = divmod(minute, MIN_PER_DAY)
    return d, m // 60
