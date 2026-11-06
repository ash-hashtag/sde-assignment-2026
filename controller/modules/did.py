"""Caller-ID (DID) health: detect degraded numbers, probe untested ones, spread load across healthy ones.

Caller IDs are randomised per dial, so within the same hours every number sees the same mix of people. Comparing
a number's pickup with the pooled pickup of the *other* numbers in the same hours is therefore a clean,
confounder-free test. We compare counts against an hour-matched expectation:

    expected_d = sum over hours h of dials_{d,h} * pickup_{others,h}
    ratio_d    = connected_d / expected_d,      z_d = (connected_d - expected_d) / sqrt(expected_d)

A number in use is pulled when, in a recent window (1h, 2h or 6h of dialling):
  * its ratio is below DID_DEGRADED_RATIO, and
  * the deficit is significant (z below DID_DEGRADED_Z: population evidence, never one call), and
  * it is a *change*: the ratio also fell by at least a quarter against the number's own previous 12 hours.
The last condition separates a number that just got flagged from one that is merely busier than a fresh number
(heavily used numbers pick up less; that is handled by rebalancing, not by pulling them).

Untested numbers are probed with a small share and judged once they have enough dials. Healthy numbers share
traffic in proportion to their measured health squared, recomputed every few hours, which keeps load moving
toward the numbers that are currently picking up best.
"""
from __future__ import annotations

from .. import settings as S
from ..ctx import WorkflowCtx
from ..intents import Intent, blend, dist_for, normalise_dist, tv
from ..stats import ratio_z
from .base import Module, daily_volume, impact_score


class DidHealth(Module):
    name = "did"

    def _stats(self, ctx: WorkflowCtx, hours: int, skip: int = 0) -> dict[str, dict]:
        """Hour-matched pickup ratio per caller ID over `hours` dialling hours, after skipping the newest `skip`."""
        keys = ctx.hour_keys(hours + skip)[skip:]
        if not keys:
            return {}
        hi_abs = keys[0][0] * 24 + keys[0][1]
        lo_abs = keys[-1][0] * 24 + keys[-1][1]
        rows = self.s.q("SELECT day, hour, did, SUM(dials), SUM(conn) FROM agg_pick WHERE wf=? "
                        "AND day>=? AND day*24+hour BETWEEN ? AND ? GROUP BY day, hour, did",
                        (ctx.wf, lo_abs // 24, lo_abs, hi_abs))
        by_h: dict[tuple, dict[str, tuple[int, int]]] = {}
        for d, h, did, n, c in rows:
            by_h.setdefault((d, h), {})[did] = (n, c)
        out: dict[str, dict] = {}
        for dids in by_h.values():
            tn = sum(n for n, _ in dids.values())
            tc = sum(c for _, c in dids.values())
            for did, (n, c) in dids.items():
                on, oc = tn - n, tc - c
                o = out.setdefault(did, {"dials": 0, "conn": 0, "expected": 0.0})
                o["dials"] += n
                o["conn"] += c
                if on > 0:
                    o["expected"] += n * oc / on
        for o in out.values():
            e = o["expected"]
            o["ratio"] = (o["conn"] + 5) / (e + 5) if e > 0 else None   # mild shrinkage toward 1
            o["z"] = ratio_z(o["conn"], e) if e > 0 else 0.0
            o["expected"] = round(e, 1)
        return out

    def _detect_degraded(self, ctx: WorkflowCtx, dids: dict, cur: dict) -> None:
        for d in [d for d in cur if dids.get(d, {}).get("status") in ("healthy", "probing")]:
            for h in (1, 2, S.DID_WINDOW_HOURS):
                o = self._stats(ctx, h).get(d)
                if not o or o["ratio"] is None:
                    continue
                if not (o["ratio"] < S.DID_DEGRADED_RATIO and o["z"] < S.DID_DEGRADED_Z):
                    continue
                prev = self._stats(ctx, 12, skip=h).get(d)
                prev_ratio = prev["ratio"] if prev and prev["ratio"] and prev["expected"] >= 30 else None
                if prev_ratio is not None and o["ratio"] / prev_ratio > 0.75:
                    continue   # persistently lower, not a new flag: rebalancing handles it
                dids[d] = {"status": "degraded", "since": ctx.now,
                           "evidence": {**o, "window_h": h, "previous_ratio": prev_ratio}}
                self.s.decide(ctx.now, ctx.wf, "did_degraded",
                              f"caller ID {d} degraded: pickup {o['ratio']:.0%} of the other numbers over the last "
                              f"{h}h ({o['conn']} connects vs {o['expected']:.0f} expected, z={o['z']:.1f}; "
                              f"previously {prev_ratio if prev_ratio is None else round(prev_ratio, 2)})",
                              {"did": d, **o, "window_h": h, "previous_ratio": prev_ratio})
                break

    def _judge_probes(self, ctx: WorkflowCtx, dids: dict) -> None:
        stats = self._stats(ctx, 24)
        for d, info in list(dids.items()):
            if info["status"] != "probing":
                continue
            o = stats.get(d)
            if not o or o["dials"] < S.DID_PROBE_MIN_DIALS or o["ratio"] is None:
                continue
            r = o["ratio"]
            if r < 0.7 and o["z"] < -3:
                verdict = "degraded"
            elif r >= 0.8 or o["dials"] >= 3 * S.DID_PROBE_MIN_DIALS:
                verdict = "healthy" if r >= 0.7 else "degraded"
            else:
                continue
            dids[d] = {"status": verdict, "since": ctx.now, "evidence": o}
            self.s.decide(ctx.now, ctx.wf, f"did_probe_{verdict}",
                          f"probe of caller ID {d} finished: {verdict} (pickup {r:.0%} of the other numbers in the "
                          f"same hours, {o['dials']} dials, z={o['z']:.1f})", {"did": d, **o})

    def intents(self, ctx: WorkflowCtx, **kw) -> list[Intent]:
        if ctx.locked_by_supervisor("caller_id", S.SUPERVISOR_LOCK_HOURS):
            return []
        st = self.load(ctx.wf, {"dids": {}, "last_rebalance": None})
        before = repr(st)
        dids = st["dids"]
        opts = ctx.options["caller_id"]
        for d in opts:
            if d not in dids:
                used = self.s.q1("SELECT SUM(dials) FROM agg_pick WHERE wf=? AND did=?", (ctx.wf, d)) or 0
                dids[d] = {"status": "healthy" if used >= S.DID_PROBE_MIN_DIALS else "unknown", "since": ctx.now}
        cur = dist_for(ctx.config, "default", "caller_id")
        if ctx.in_window():
            self._detect_degraded(ctx, dids, cur)
            self._judge_probes(ctx, dids)

        degraded = [d for d in opts if dids[d]["status"] == "degraded"]
        unknown = [d for d in opts if dids[d]["status"] == "unknown"]
        target = dict(cur)
        reasons, urgent = [], False
        live_bad = [d for d in degraded if cur.get(d, 0) > 0]
        if live_bad:
            for d in live_bad:
                target.pop(d)
            healthy = [d for d in opts if dids[d]["status"] == "healthy"]
            if healthy:
                # spread evenly over every healthy number: piling the freed traffic onto whichever number was
                # already busiest would wear that one out next
                probe = {d: v for d, v in target.items() if dids[d]["status"] == "probing"}
                rest = 1 - sum(probe.values())
                target = {**probe, **{d: rest / len(healthy) for d in healthy}}
            if not target:   # every number degraded: keep the least bad rather than stop dialling
                target = {max(cur, key=cur.get): 1.0}
            reasons.append(f"stop dialling from degraded caller ID(s) {', '.join(live_bad)}")
            urgent = True
        else:
            if unknown and not any(i["status"] == "probing" for i in dids.values()) and ctx.in_window():
                # one probe at a time where we can auto-apply; all at once where every change costs an approval
                for d in (unknown[:1] if ctx.auto_allowed("caller_id") else unknown[:2]):
                    dids[d] = {"status": "probing", "since": ctx.now}
            probing = [d for d in opts if dids[d]["status"] == "probing"]
            missing = [d for d in probing if target.get(d, 0) < S.DID_PROBE_SHARE / 2]
            if missing:
                keep = 1 - S.DID_PROBE_SHARE * len(missing)
                target = {k: v * keep for k, v in target.items()}
                for d in missing:
                    target[d] = S.DID_PROBE_SHARE
                reasons.append(f"probe untested caller ID(s) {', '.join(missing)} at {S.DID_PROBE_SHARE:.0%} each")
            else:
                reb = self._rebalance(ctx, st, dids, cur, probing)
                if reb:
                    target, why = reb
                    reasons.append(why)
        if repr(st) != before:
            self.save(ctx.wf, st)
        target = normalise_dist(target)
        if not reasons or tv(target, cur) < 1e-6:
            return []
        return [self._intent(ctx, cur, target, "; ".join(reasons), urgent, dids)]

    def _rebalance(self, ctx, st, dids, cur, probing):
        healthy = [d for d in ctx.options["caller_id"] if dids[d]["status"] == "healthy"]
        pending = st.get("pending_rebalance")
        if pending:
            # keep asking for a computed target until it is live (governance may be waiting on quota, an approval in
            # flight, or approver hours); recompute only once it is a day old
            if tv(normalise_dist(pending["target"]), cur) < 1e-3:
                st.pop("pending_rebalance")
                st["last_rebalance"] = ctx.now
                return None
            if ctx.now - pending["at"] < 24 * 60 and all(d in healthy for d in pending["target"]):
                return pending["target"], pending["reason"]
            st.pop("pending_rebalance")
        last = st.get("last_rebalance")
        if not ctx.in_window() or len(healthy) < 2:
            return None
        if last is not None and ctx.now - last < S.DID_REBALANCE_EVERY_HOURS * 60:
            return None
        stats = self._stats(ctx, 12)
        if any(stats.get(d, {}).get("dials", 0) < 100 for d in healthy if cur.get(d)):
            return None
        # shrink each measured ratio toward 1 unless its difference is significant, so noise doesn't move traffic
        ratios = {}
        for d in healthy:
            o = stats.get(d) or {}
            r, z = o.get("ratio") or 1.0, abs(o.get("z") or 0.0)
            ratios[d] = 1 + (r - 1) * min(1.0, z / 3)
        best = max(ratios.values())
        w = {d: max((r / best) ** 2, 0.25) for d, r in ratios.items()}
        probe_share = {d: cur[d] for d in probing if d in cur}
        cand = {d: w[d] * (1 - sum(probe_share.values())) / sum(w.values()) for d in healthy}
        cand.update(probe_share)
        cand = normalise_dist(cand)
        # where every change costs a human's attention, only move for a bigger difference
        min_tv = S.DID_REBALANCE_MIN_TV * (1 if ctx.auto_allowed("caller_id") else 2)
        if tv(cand, cur) < min_tv:
            st["last_rebalance"] = ctx.now
            return None
        if ctx.auto_allowed("caller_id"):
            # one policy-sized step per rebalance cycle, so it stays an auto-apply instead of using a human's slot;
            # the 6h cadence means this is not a chain of steps around max_shift
            limit = float((ctx.gov.get("auto_apply") or {}).get("max_shift", 0))
            shift = tv(cand, cur)
            if limit > 0 and shift > limit:
                cand = blend(cur, cand, limit / shift * 0.99)
        reason = ("rebalance load across healthy caller IDs by measured pickup ("
                  + ", ".join(f"{d} {ratios[d]:.2f}" for d in healthy) + ")")
        st["pending_rebalance"] = {"target": cand, "reason": reason, "at": ctx.now}
        return cand, reason

    def _intent(self, ctx, cur, target, reason, urgent, dids) -> Intent:
        stats = self._stats(ctx, 24)
        health = {d: (stats.get(d) or {}).get("ratio") or 1.0 for d in ctx.options["caller_id"]}
        exp_old = sum(p * health[d] for d, p in cur.items())
        exp_new = sum(p * health[d] for d, p in target.items())
        gain = (exp_new / exp_old - 1) if exp_old else 0.0
        vol = daily_volume(ctx)
        extra = gain * vol["dials_per_day"] * vol["pickup"] * vol["engagement"]
        affected = ctx.active_leads() if ctx.spec["mid_flight"] == "allowed" else ctx.spec["daily_batch"]["size"]
        impact = impact_score(ctx, extra)
        return Intent(
            source="did", path=["allocations", "default", "caller_id"], value=target,
            summary=reason, urgent=urgent, step_ok=urgent, auto="prefer",
            rationale=(f"{reason}. Caller IDs are randomised per dial, so each number's pickup is compared with the "
                       f"other numbers in the same hours. Relative pickup over the last 24 dialling hours: "
                       + ", ".join(f"{d}={health[d]:.2f}" for d in sorted(health)) + "."),
            dry_run={"method": "hour-matched pickup ratio per caller ID over the last 24 dialling hours, "
                               "weighted by the new allocation",
                     "relative_health": {d: round(h, 3) for d, h in sorted(health.items())},
                     "expected_pickup_change": round(gain, 4),
                     "expected_extra_conclusions_per_day": round(extra, 1),
                     "status": {d: dids[d]["status"] for d in sorted(dids)}},
            impact=max(0.8, impact) if urgent else impact,
            affected_leads=int(affected), ref=f"did:{ctx.wf}")
