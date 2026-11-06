"""Call time per cohort, learned from history; owner of the shared cohort partition.

Cohorts. One partition per workflow, age_band x city_tier, keeping segments with at least
SCHEDULE_MIN_SEGMENT_SHARE of leads (the rest fall to `default`). The same cohort ids are used by the schedule, the
supervisor view and segment reporting. Experiments allocate at `default` level, which every cohort inherits, so the
partition never fragments experiment traffic.

Hour weights. History ran a flat schedule, so pickup by (segment, hour) in history is an unconfounded estimate.
The dialler picks among eligible leads in proportion to their weight, so what matters is each segment's
*comparative* advantage in an hour: weight = (pickup(seg, h) / mean_h pickup(seg, .)) ** gamma. Cells are shrunk
toward a multiplicative segment x hour model so thin cells don't produce wild weights.

Dry run. Iterative proportional fitting re-distributes historical dials so each hour keeps its capacity and each
segment keeps its total attempts, with the new weights tilting who is called when. Expected pickup under that
redistribution vs. history is the predicted lift; gamma is chosen from {1, 2, 3} by that prediction, and nothing is
proposed below a 1% predicted lift.
"""
from __future__ import annotations

import numpy as np

from .. import settings as S
from ..ctx import WorkflowCtx
from ..intents import Intent, same_value
from .base import Module, daily_volume, impact_score

SHRINK_DIALS = 200


def cohort_id(age: str, tier: str) -> str:
    return "age_" + age.replace("+", "plus").replace("-", "_") + f"_t{tier}"


class Schedule(Module):
    name = "schedule"

    def _fit(self, ctx: WorkflowCtx) -> dict | None:
        lo, hi = ctx.window
        hours = list(range(lo, hi))
        rows = self.s.q("SELECT a.age_band, a.city_tier, p.hour, SUM(p.dials), SUM(p.conn) FROM agg_pick p "
                        "JOIN atoms a ON a.id = p.atom WHERE p.wf=? AND p.day<0 GROUP BY 1, 2, 3", (ctx.wf,))
        if not rows:
            return None
        segs = sorted({(a, t) for a, t, *_ in rows})
        si = {s: i for i, s in enumerate(segs)}
        D = np.zeros((len(segs), len(hours)))
        C = np.zeros_like(D)
        for a, t, h, n, c in rows:
            if lo <= h < hi:
                D[si[(a, t)], h - lo] += n
                C[si[(a, t)], h - lo] += c
        total = D.sum()
        if total < 2000:
            return None
        share = D.sum(axis=1) / total
        keep = [i for i in range(len(segs)) if share[i] >= S.SCHEDULE_MIN_SEGMENT_SHARE][:19]
        # multiplicative prior: segment level x hour shape
        seg_rate = (C.sum(axis=1) + 1) / (D.sum(axis=1) + 4)
        hour_rate = (C.sum(axis=0) + 1) / (D.sum(axis=0) + 4)
        overall = C.sum() / total
        prior = np.outer(seg_rate, hour_rate) / overall
        R = (C + SHRINK_DIALS * prior) / (D + SHRINK_DIALS)
        rel = R / R.mean(axis=1, keepdims=True)
        base_pick = (D * R).sum() / total
        best = None
        for gamma in (1.0, 2.0, 3.0):
            W = np.clip(rel ** gamma, S.SCHEDULE_MIN_WEIGHT, 5.0)
            Dn = _ipf(D * W, D.sum(axis=1), D.sum(axis=0))
            pick = (Dn * R).sum() / total
            if best is None or pick > best[1]:
                best = (gamma, pick, W)
        gamma, pick, W = best
        cohorts, weights = [], {}
        for i in keep:
            a, t = segs[i]
            cid = cohort_id(a, t)
            cohorts.append({"id": cid, "where": {"age_band": [a], "city_tier": [t]}})
            weights[cid] = {str(h): round(float(W[i, j]), 3) for j, h in enumerate(hours)}
        return {"cohorts": cohorts, "hour_weights": weights, "gamma": gamma,
                "predicted_pickup_lift": float(pick / base_pick - 1), "history_pickup": float(base_pick),
                "dials": int(total)}

    def intents(self, ctx: WorkflowCtx, **kw) -> list[Intent]:
        if ctx.locked_by_supervisor("schedule", S.SUPERVISOR_LOCK_HOURS) or \
                ctx.locked_by_supervisor("cohorts", S.SUPERVISOR_LOCK_HOURS):
            return []
        st = self.load(ctx.wf)
        if "plan" not in st:
            plan = self._fit(ctx)
            if plan is None:
                return []
            st["plan"] = plan
            self.save(ctx.wf, st)
            self.s.decide(ctx.now, ctx.wf, "schedule_fit",
                          f"call-time model from history: {len(plan['cohorts'])} cohorts, gamma={plan['gamma']}, "
                          f"predicted pickup lift {plan['predicted_pickup_lift']:+.1%}", plan)
        plan = st["plan"]
        if plan["predicted_pickup_lift"] < 0.01:
            return []
        vol = daily_volume(ctx)
        extra = plan["predicted_pickup_lift"] * vol["dials_per_day"] * vol["pickup"] * vol["engagement"]
        cohorts_live = same_value(ctx.config.get("cohorts", []), plan["cohorts"])
        dry = {"method": "IPF redistribution of historical dials (hour capacity and per-cohort attempts held fixed) "
                         "under the new weights, scored with history's pickup by cohort and hour",
               "history_pickup": round(plan["history_pickup"], 4),
               "predicted_pickup_lift": round(plan["predicted_pickup_lift"], 4),
               "gamma": plan["gamma"], "history_dials": plan["dials"]}
        out = []
        if not cohorts_live:
            out.append(Intent(
                source="schedule", path=["cohorts"], value=plan["cohorts"],
                summary=f"Define {len(plan['cohorts'])} cohorts (age band x city tier) used for call timing and reporting",
                rationale="One shared cohort partition per workflow. Cohorts carry no allocation of their own, so "
                          "welcome message, voice and caller ID are unchanged by this.",
                dry_run={"method": "lead counts per cohort from history", "cohorts": plan["cohorts"]},
                impact=0.0, affected_leads=0, auto="never", ref=f"schedule:{ctx.wf}"))
        cur = (ctx.config.get("schedule") or {}).get("hour_weights") or {}
        if not same_value(cur, plan["hour_weights"]):
            out.append(Intent(
                source="schedule", path=["schedule", "hour_weights"], value=plan["hour_weights"],
                summary=f"Call each cohort in its better hours (predicted pickup {plan['predicted_pickup_lift']:+.1%})",
                rationale=(f"History ran a flat schedule over {plan['dials']} dials, so pickup by cohort and hour is "
                           f"unconfounded. Each cohort is tilted toward hours where it picks up better than its own "
                           f"average (gamma={plan['gamma']}); every hour keeps a non-zero weight so no capacity goes "
                           f"unused. Who is called changes, not how many calls are made."),
                dry_run=dry, impact=impact_score(ctx, extra), affected_leads=ctx.active_leads(),
                auto="prefer" if cohorts_live else "never", ref=f"schedule:{ctx.wf}"))
        return out


def _ipf(M: np.ndarray, rows: np.ndarray, cols: np.ndarray, iters: int = 50) -> np.ndarray:
    X = M.copy()
    for _ in range(iters):
        X *= (rows / np.maximum(X.sum(axis=1), 1e-12))[:, None]
        X *= (cols / np.maximum(X.sum(axis=0), 1e-12))[None, :]
    return X
