"""Welcome-message and voice experiments: explore -> promote with a holdout -> watch for decay -> roll back.

Design
  * Factorial: welcome_message and voice are randomised independently on every dial, so one allocation that
    splits both dimensions tests both at once, and each dimension's comparison uses all the traffic.
  * Exploration keeps EXPLORE_INCUMBENT_SHARE on the current option; challengers split the rest. That bounds what
    a bad challenger can cost while it is being found out.
  * Only calls that actually ran with an arm count as evidence for it (the call event's own `variant`), from the
    moment the exploration allocation went live. Arms that never got traffic have no evidence, whatever a config
    said.
  * Winner: Beta-Binomial posterior on engagement (engaged / connected). Promote a challenger when
    P(best) >= P_BEST_TO_PROMOTE, P(beats incumbent) >= P_BEATS_INCUMBENT, every arm has MIN_CONN_PER_ARM, and the
    last 24 dialling hours still agree (a winner that is already fading is not promoted). P(best) across all arms
    is the multiple-comparison guard: one decision per dimension, not one test per arm.
  * Promotion keeps HOLDOUT_SHARE on the previous option. The holdout is how decay is detected: when the
    posterior over the trailing window says the winner is now worse than the holdout with P >= P_DECAY_ROLLBACK,
    roll back (urgent; auto-applied in max_shift steps where policy allows).
  * Every change here is customer-facing, so it always goes to a human, even where policy would allow auto-apply.
    Rollbacks are the exception: they reduce risk and may auto-apply where permitted.
"""
from __future__ import annotations

from .. import settings as S
from ..ctx import WorkflowCtx
from ..intents import Intent, dist_for, normalise_dist, same_value
from ..simtime import fmt
from ..stats import compare_arms
from .base import Module, daily_volume, impact_score

DIMS = ("welcome_message", "voice")
COL = {"welcome_message": "wm", "voice": "voice"}


class Experiments(Module):
    name = "experiments"

    def _arm_counts(self, ctx: WorkflowCtx, dim: str, since_minute: int, until_minute: int | None = None,
                    arms: list[str] | None = None) -> dict[str, tuple[int, int]]:
        sql = (f"SELECT {COL[dim]}, SUM(eng), SUM(conn) FROM agg_eng WHERE wf=? AND day*24+hour>=?"
               + (" AND day*24+hour<?" if until_minute is not None else "") + f" GROUP BY {COL[dim]}")
        args = [ctx.wf, since_minute // 60] + ([until_minute // 60] if until_minute is not None else [])
        out = {a: (int(e), int(c)) for a, e, c in self.s.q(sql, args)}
        if arms is not None:
            out = {a: out.get(a, (0, 0)) for a in arms}
        return out

    def _explore_target(self, incumbent: str, challengers: list[str]) -> dict:
        if not challengers:
            return {incumbent: 1.0}
        share = min((1 - S.EXPLORE_INCUMBENT_SHARE) / len(challengers), S.MAX_CHALLENGER_SHARE)
        return normalise_dist({incumbent: 1 - share * len(challengers), **{c: share for c in challengers}})

    def intents(self, ctx: WorkflowCtx, **kw) -> list[Intent]:
        st = self.load(ctx.wf, {"exps": {}, "seq": 0})
        out = []
        for dim in DIMS:
            it = self._dim(ctx, st, dim)
            if it:
                out.append(it)
        self.save(ctx.wf, st)
        return out

    def _new_exp(self, ctx, st, dim, cur) -> dict | None:
        opts = ctx.options[dim]
        if len(opts) < 2:
            return None
        if ctx.end is not None and ctx.end - ctx.now < S.MIN_DAYS_LEFT_TO_EXPLORE * 1440:
            return None
        incumbent = max(cur, key=cur.get)
        old = st["exps"].get(dim) or {}
        bad = set(old.get("decayed", [])) | set(old.get("dropped", {}))
        challengers = [o for o in opts if o != incumbent and o not in bad]
        if not challengers:
            return None
        st["seq"] += 1
        exp = {"id": f"exp-{ctx.wf}-{dim}-{st['seq']}", "dim": dim, "phase": "explore", "incumbent": incumbent,
               "arms": [incumbent] + challengers, "dropped": dict(old.get("dropped", {})),
               "decayed": list(old.get("decayed", [])), "target": self._explore_target(incumbent, challengers),
               "started": ctx.now, "live_since": None}
        self.s.decide(ctx.now, ctx.wf, "experiment_planned",
                      f"{exp['id']}: test {', '.join(challengers)} against {incumbent} on {dim}", exp, ref=exp["id"])
        return exp

    def _dim(self, ctx: WorkflowCtx, st: dict, dim: str) -> Intent | None:
        cur = dist_for(ctx.config, "default", dim)
        exp = st["exps"].get(dim)
        if ctx.locked_by_supervisor(dim, S.SUPERVISOR_LOCK_HOURS):
            if exp and exp["phase"] != "closed" and not exp.get("superseded"):
                exp["phase"], exp["superseded"] = "closed", ctx.now
                self.s.decide(ctx.now, ctx.wf, "experiment_closed",
                              f"{exp['id']} stopped: a supervisor changed {dim} at {fmt(ctx.supervisor_dims[dim])}; "
                              f"their choice stands", {"current": cur}, ref=exp["id"])
            return None
        if exp is None or (exp["phase"] == "closed" and exp.get("superseded")):
            exp = self._new_exp(ctx, st, dim, cur)
            if exp is None:
                return None
            st["exps"][dim] = exp
        if exp["phase"] == "closed":
            return None

        live = same_value(cur, exp["target"])
        if live and exp["phase"] in ("rollback", "closing"):
            exp["phase"] = "closed"
            self.s.decide(ctx.now, ctx.wf, "experiment_settled", f"{exp['id']}: {dim} settled on {exp['target']}",
                          ref=exp["id"])
            return None
        if live and exp["live_since"] is None:
            exp["live_since"] = ctx.now
            self.s.decide(ctx.now, ctx.wf, "experiment_live", f"{exp['id']} {exp['phase']} allocation live: "
                          f"{exp['target']}", ref=exp["id"])
        if not live:
            return self._intent(ctx, exp, cur)
        if exp["phase"] == "explore":
            self._evaluate_explore(ctx, exp)
        elif exp["phase"] == "exploit":
            self._monitor(ctx, exp)
        if not same_value(cur, exp["target"]):
            return self._intent(ctx, exp, cur)
        return None

    # ------------------------------------------------------------------ decisions
    def _evaluate_explore(self, ctx: WorkflowCtx, exp: dict):
        arms = [a for a in exp["arms"] if a not in exp["dropped"]]
        counts = self._arm_counts(ctx, exp["dim"], exp["live_since"], arms=arms)
        inc = exp["incumbent"]
        if any(c[1] < S.MIN_CONN_PER_ARM for c in counts.values()):
            if ctx.now - exp["live_since"] > S.MAX_EXPLORE_DAYS * 1440:
                self._close(ctx, exp, counts, "ran out of time before every arm had enough calls")
            return
        res = compare_arms(counts, inc)
        exp["last_eval"] = {"at": ctx.now, "arms": res}
        best = max(res, key=lambda a: res[a]["p_best"])
        if best != inc and res[best]["p_best"] >= S.P_BEST_TO_PROMOTE \
                and res[best]["p_beats_incumbent"] >= S.P_BEATS_INCUMBENT:
            recent = self._arm_counts(ctx, exp["dim"], max(exp["live_since"], ctx.now - 24 * 60), arms=[best, inc])
            rr = compare_arms(recent, inc) if all(c[1] >= 50 for c in recent.values()) else None
            if rr and rr[best]["p_beats_incumbent"] < 0.6:
                if not exp.get("trend_hold"):
                    exp["trend_hold"] = ctx.now
                    self.s.decide(ctx.now, ctx.wf, "experiment_hold",
                                  f"{exp['id']}: {best} leads overall but not over the last 24h "
                                  f"(P(beats {inc})={rr[best]['p_beats_incumbent']:.2f}); not promoting a fading winner",
                                  {"overall": res, "recent": rr}, ref=exp["id"])
                return
            exp.update(phase="exploit", winner=best, holdout=inc, promoted_decision=ctx.now, live_since=None,
                       target=normalise_dist({best: 1 - S.HOLDOUT_SHARE, inc: S.HOLDOUT_SHARE}),
                       evidence=res)
            self.s.decide(ctx.now, ctx.wf, "experiment_winner",
                          f"{exp['id']}: {best} beats {inc} on engagement (P(best)={res[best]['p_best']:.3f}, "
                          f"lift {res[best]['lift']:+.1%} [{res[best]['lift_ci'][0]:+.1%}, {res[best]['lift_ci'][1]:+.1%}]"
                          f", n={res[best]['n']}); promote with {S.HOLDOUT_SHARE:.0%} holdout on {inc}",
                          {"arms": res}, ref=exp["id"])
            return
        dropped = [a for a in res if a != inc and res[a]["p_beats_incumbent"] <= S.P_LOSER_DROP]
        # an arm can also lose *recently*: effects that fade after exposure look fine on all-time data
        recent = self._arm_counts(ctx, exp["dim"], max(exp["live_since"], ctx.now - S.DECAY_WINDOW_HOURS * 60),
                                  arms=arms)
        if all(c[1] >= S.MIN_HOLDOUT_CONN for c in recent.values()):
            rres = compare_arms(recent, inc)
            dropped += [a for a in rres if a != inc and a not in dropped
                        and rres[a]["p_beats_incumbent"] <= 1 - S.P_DECAY_ROLLBACK]
        for a in dropped:
            exp["dropped"][a] = {"at": ctx.now, "stats": res[a]}
        if dropped:
            left = [a for a in arms if a not in dropped and a != inc]
            exp["target"] = self._explore_target(inc, left)
            exp["live_since_prev"] = exp["live_since"]
            self.s.decide(ctx.now, ctx.wf, "experiment_drop",
                          f"{exp['id']}: dropping {', '.join(dropped)} (P(beats {inc}) <= {S.P_LOSER_DROP})",
                          {"arms": res}, ref=exp["id"])
            if not left:
                self._close(ctx, exp, counts, f"every challenger lost to {inc}", res)
            return
        if res[inc]["p_best"] >= S.P_BEST_TO_PROMOTE:
            self._close(ctx, exp, counts, f"{inc} is best (P={res[inc]['p_best']:.3f})", res)
        elif ctx.now - exp["live_since"] > S.MAX_EXPLORE_DAYS * 1440:
            self._close(ctx, exp, counts, "no arm reached the promotion bar in time; keeping the incumbent", res)

    def _close(self, ctx, exp, counts, why, res=None):
        """End exploration without a declared winner.

        Reverting to the incumbent throws away what we learned (and is itself harmful when a challenger was
        quietly better). Instead traffic is split in proportion to each arm's posterior probability of being best,
        keeping only the incumbent and challengers more likely than not to beat it, and dropping arms below 10%
        P(best): an undecided experiment settles on the arms the evidence favours, and the
        allocation still carries comparison traffic so a later look can conclude. No arm is called a winner.
        """
        survivors = [a for a in (res or {}) if a not in exp["dropped"]]
        if res and len(survivors) > 1:
            keep = {a: res[a]["p_best"] for a in survivors if res[a]["p_best"] >= 0.10
                    and (a == exp["incumbent"] or res[a]["p_beats_incumbent"] >= 0.5)}
            target = normalise_dist(keep) if keep else {exp["incumbent"]: 1.0}
        else:
            target = {exp["incumbent"]: 1.0}
        # removing traffic from options that lost is worth a request on its own; re-weighting a draw is not
        exp.update(phase="closing", target=target, closed=ctx.now, live_since=None,
                   piggyback=len(survivors) > 1)
        self.s.decide(ctx.now, ctx.wf, "experiment_closed", f"{exp['id']} closed: {why}; settle on {target}",
                      {"arms": res or counts}, ref=exp["id"])

    def _monitor(self, ctx: WorkflowCtx, exp: dict):
        w, h = exp["winner"], exp["holdout"]
        since = max(exp["live_since"], ctx.now - S.DECAY_WINDOW_HOURS * 60)
        counts = self._arm_counts(ctx, exp["dim"], since, arms=[w, h])
        if counts[h][1] < S.MIN_HOLDOUT_CONN:
            return
        res = compare_arms(counts, h)
        exp["last_eval"] = {"at": ctx.now, "arms": res}
        p_worse = 1 - res[w]["p_beats_incumbent"]
        if p_worse >= S.P_DECAY_ROLLBACK:
            exp["decayed"].append(w)
            exp.update(phase="rollback", target={h: 1.0}, rolled_back=ctx.now, incumbent=h, live_since=None)
            self.s.decide(ctx.now, ctx.wf, "experiment_decay",
                          f"{exp['id']}: {w} has stopped winning: over the last {S.DECAY_WINDOW_HOURS}h it is "
                          f"{res[w]['lift']:+.1%} vs holdout {h} (P(worse)={p_worse:.2f}); rolling back to {h}",
                          {"arms": res}, ref=exp["id"])

    # ------------------------------------------------------------------ intents
    def _intent(self, ctx: WorkflowCtx, exp: dict, cur: dict) -> Intent | None:
        phase = exp["phase"]
        dim, target = exp["dim"], exp["target"]
        vol = daily_volume(ctx)
        ev = (exp.get("last_eval") or {}).get("arms") or exp.get("evidence") or {}
        means = {a: v["mean"] for a, v in ev.items()}
        base_mean = means.get(exp["incumbent"], vol["engagement"])
        exp_old = sum(p * means.get(a, base_mean) for a, p in cur.items())
        exp_new = sum(p * means.get(a, base_mean) for a, p in target.items())
        extra = (exp_new - exp_old) * vol["conn_per_day"]
        affected = ctx.active_leads() if ctx.spec["mid_flight"] == "allowed" else ctx.spec["daily_batch"]["size"]
        no_data = [a for a in target if a not in means]
        dry = {"method": "posterior mean engagement per arm from calls that actually ran with it, replayed over "
                         "the last 3 days of connected-call volume",
               "engagement_old": round(exp_old, 4), "engagement_new": round(exp_new, 4),
               "connected_per_day": round(vol["conn_per_day"]), "extra_conclusions_per_day": round(extra, 1),
               "arms": ev, "arms_without_evidence_assumed_equal_to_incumbent": no_data}
        if phase == "explore":
            summary = f"Test {dim} options " + ", ".join(f"{a} {p:.0%}" for a, p in sorted(target.items()))
            rationale = (f"{exp['id']}: no evidence yet on {', '.join(a for a in target if a != exp['incumbent'])}. "
                         f"{exp['incumbent']} keeps {target.get(exp['incumbent'], 0):.0%} of traffic so a weak option "
                         f"costs little. A challenger is promoted only at P(best) >= {S.P_BEST_TO_PROMOTE} with "
                         f">= {S.MIN_CONN_PER_ARM} connected calls per arm; clear losers are dropped early.")
            impact, urgent, auto = impact_score(ctx, extra), False, "never"
        elif phase == "exploit":
            w = exp["winner"]
            r = exp["evidence"][w]
            summary = (f"Promote {dim} {w} to {target[w]:.0%} (keep {exp['holdout']} at {target[exp['holdout']]:.0%} "
                       f"as holdout)")
            rationale = (f"{exp['id']}: {w} lifted engagement {r['lift']:+.1%} (95% interval {r['lift_ci'][0]:+.1%} "
                         f"to {r['lift_ci'][1]:+.1%}) over {exp['holdout']} on {r['n']} connected calls; "
                         f"P(best)={r['p_best']:.3f}. The holdout lets us detect if the effect fades and roll back.")
            impact, urgent, auto = impact_score(ctx, extra), False, "never"
        elif phase == "rollback":
            summary = f"Set {dim} back to {exp['incumbent']} (promoted option faded)"
            rationale = f"{exp['id']}: the promoted option is now worse than the holdout; reverting."
            urgent = True
            impact = max(impact_score(ctx, extra), 0.6)
            auto = "prefer"
        else:  # closing
            summary = f"End {dim} test: " + ", ".join(f"{a} {p:.0%}" for a, p in sorted(target.items()))
            rationale = (f"{exp['id']}: no option reached the promotion bar; traffic follows each option's "
                         f"probability of being best, dropping unlikely ones.")
            impact, urgent, auto = impact_score(ctx, extra), False, "never"
        return Intent(source="experiment", path=["allocations", "default", dim], value=target, summary=summary,
                      rationale=rationale, dry_run=dry, impact=impact, affected_leads=int(affected), urgent=urgent,
                      auto=auto, step_ok=urgent, piggyback=phase == "closing" and exp.get("piggyback", True),
                      ref=exp["id"])
