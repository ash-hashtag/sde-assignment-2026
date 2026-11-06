"""Hallucination incidents: detect -> pick a fix -> validate -> propose with evidence -> verify after apply.

Detection compares hallucination flags on the *current* prompt over short and long windows (QA_WINDOWS_HOURS) of
dialling with the workflow's normal flag rate (learned from history). It fires only when the count is at least
QA_MIN_FLAGS, at least QA_MIN_RATIO x normal, and has a Poisson tail probability below QA_P_VALUE (a much lower
bar, QA_*_RECENT, applies within 24h of a prompt change, which is where regressions come from). The flag is
an imperfect detector with a false-positive floor, which the baseline absorbs.

Fix selection, cheapest first:
  1. a prompt this workflow already ran in production with a normal flag rate (usually the one before the
     incident): no LLM call needed;
  2. otherwise ask the LLM for alternatives (3 credits) and validate them.
Every candidate is validated (VALIDATION_N conversations, 2 credits) before it is proposed, because approvers
require it and because "the model thinks it's better" isn't evidence. Validation only measures safety, so after
the fix is live we also check engagement didn't fall (a strict, word-for-word script can be safe and useless).
"""
from __future__ import annotations

from .. import settings as S
from ..ctx import WorkflowCtx
from ..intents import Intent
from ..simtime import fmt
from ..stats import compare_arms, poisson_sf
from .base import Module, daily_volume, impact_score


class Incidents(Module):
    name = "incidents"

    def _baseline(self, ctx: WorkflowCtx) -> float:
        st = self.load(ctx.wf)
        if "baseline" not in st:
            c, f = self.s.q("SELECT COALESCE(SUM(conn),0), COALESCE(SUM(flags),0) FROM agg_qa WHERE wf=? AND day<0",
                            (ctx.wf,))[0]
            st["baseline"] = (f + 1) / (c + 100) if c else 0.015
            st["baseline_n"] = c
            self.save(ctx.wf, st)
        return st["baseline"]

    def _window(self, ctx: WorkflowCtx, prompt: str, hours: int) -> tuple[int, int, int]:
        keys = ctx.hour_keys(hours)
        if not keys:
            return 0, 0, 0
        lo = keys[-1][0] * 24 + keys[-1][1]
        r = self.s.q("SELECT COALESCE(SUM(conn),0), COALESCE(SUM(flags),0), COALESCE(SUM(eng),0) FROM agg_qa "
                     "WHERE wf=? AND prompt=? AND day*24+hour>=?", (ctx.wf, prompt, lo))[0]
        return r

    def _prompt_record(self, ctx: WorkflowCtx) -> dict[str, dict]:
        rows = self.s.q("SELECT prompt, SUM(conn), SUM(flags), SUM(eng) FROM agg_qa WHERE wf=? GROUP BY prompt",
                        (ctx.wf,))
        return {p: {"conn": c, "flags": f, "eng": e} for p, c, f, e in rows}

    def intents(self, ctx: WorkflowCtx, credits: float = 0, **kw) -> list[Intent]:
        st = self.load(ctx.wf)
        base = self._baseline(ctx)
        prompt = ctx.config["prompt_version"]
        inc = st.get("open")
        if inc is None:
            if ctx.in_window():
                inc = self._detect(ctx, prompt, base)
                if inc:
                    st = self.load(ctx.wf)
                    st["open"] = inc
                    self.save(ctx.wf, st)
            if inc is None:
                return []
        return self._advance(ctx, st, inc, prompt, base, credits)

    def _detect(self, ctx: WorkflowCtx, prompt: str, base: float) -> dict | None:
        # A prompt that changed in the last 24h is where regressions come from, so it is watched with a lower bar
        # (still population-level: several flags and a small tail probability).
        changed = self.s.q1("SELECT MAX(applied_minute) FROM config_versions WHERE wf=? AND changed_dims LIKE "
                            "'%prompt_version%'", (ctx.wf,))
        recent = changed is not None and ctx.now - changed <= 24 * 60
        min_flags, p_max = (S.QA_MIN_FLAGS_RECENT, S.QA_P_VALUE_RECENT) if recent else (S.QA_MIN_FLAGS, S.QA_P_VALUE)
        for hours in S.QA_WINDOWS_HOURS:
            c, f, _ = self._window(ctx, prompt, hours)
            e = c * base
            if f >= min_flags and e > 0 and f / e >= S.QA_MIN_RATIO and poisson_sf(f, e) < p_max:
                inc = {"id": f"inc-{ctx.wf}-{ctx.now}", "bad_prompt": prompt, "opened": ctx.now, "phase": "detected",
                       "evidence": {"window_h": hours, "connected": c, "flags": f, "expected": round(e, 1),
                                    "rate": round(f / c, 4), "baseline_rate": round(base, 4),
                                    "p_value": poisson_sf(f, e)},
                       "tried": [], "llm_used": False}
                sup = ctx.supervisor_dims.get("prompt_version")
                inc["supervisor_change_at"] = sup
                self.s.decide(ctx.now, ctx.wf, "incident_opened",
                              f"hallucination spike on prompt {prompt}: {f} flags in {c} connected calls over {hours}h "
                              f"({f / c:.1%} vs normal {base:.1%}, p={poisson_sf(f, e):.1e})"
                              + (f"; prompt was set by a supervisor at {fmt(sup)}" if sup is not None else ""),
                              inc["evidence"], ref=inc["id"])
                return inc
        return None

    def _candidates(self, ctx: WorkflowCtx, inc: dict, base: float) -> list[str]:
        rec = self._prompt_record(ctx)
        good = [p for p, r in rec.items()
                if p != inc["bad_prompt"] and p not in inc["tried"] and r["conn"] >= 300
                and (r["flags"] + 1) / (r["conn"] + 100) <= 1.5 * base and p in ctx.options["prompt_version"]]
        # most production evidence first
        return sorted(good, key=lambda p: -rec[p]["conn"]) + [p for p in inc.get("llm", []) if p not in inc["tried"]
                                                              and p not in good]

    def _validate(self, ctx: WorkflowCtx, prompt: str) -> dict | None:
        vals = self.s.state_get("validations", ctx.wf, [])
        for v in vals:
            if v["prompt_version"] == prompt and ctx.now - v["minute"] <= 48 * 60:
                return v
        r = self.c.post("/validation/runs", {"workflow_id": ctx.wf, "prompt_version": prompt, "n": S.VALIDATION_N})
        if not r.ok:
            self.s.decide(ctx.now, ctx.wf, "alert", f"validation of {prompt} failed: {r.body}", {"severity": "page"})
            return None
        v = {**r.body, "minute": ctx.now}
        vals.append(v)
        self.s.state_set("validations", ctx.wf, vals)
        self.s.decide(ctx.now, ctx.wf, "validation_run",
                      f"validated {prompt}: pass rate {v['pass_rate']:.3f} on n={v['n']} ({v['validation_run_id']})",
                      v, ref=v["validation_run_id"])
        return v

    def _advance(self, ctx, st, inc, prompt, base, credits) -> list[Intent]:
        min_pass = ctx.gov.get("min_validation_pass_rate", 0.97)
        if inc["phase"] in ("detected", "proposing") and prompt != inc["bad_prompt"]:
            # someone (us, or a supervisor) moved off the bad prompt
            inc["phase"] = "verifying"
            inc["fix"] = prompt
            inc["applied"] = ctx.now
            self.s.decide(ctx.now, ctx.wf, "incident_fix_live", f"prompt is now {prompt}; verifying", ref=inc["id"])
        if inc["phase"] == "detected":
            for p in self._candidates(ctx, inc, base):
                if credits < 2:
                    break
                v = self._validate(ctx, p)
                inc["tried"].append(p)
                if v and v["pass_rate"] >= min_pass:
                    inc["phase"] = "proposing"
                    inc["fix"] = p
                    inc["validation"] = v
                    break
            else:
                if not inc["llm_used"] and credits >= 3 + 2:
                    r = self.c.post("/llm/suggest-fixes", {"workflow_id": ctx.wf, "problem": (
                        f"hallucination flag rate {inc['evidence']['rate']:.1%} on prompt {inc['bad_prompt']} "
                        f"vs normal {base:.1%}")})
                    inc["llm_used"] = True
                    if r.ok:
                        inc["llm"] = [s["prompt_version"] for s in r.body["suggestions"]]
                        self.s.decide(ctx.now, ctx.wf, "llm_suggest", f"LLM suggested {inc['llm']}", r.body,
                                      ref=inc["id"])
                elif inc["phase"] == "detected" and not inc.get("escalated"):
                    inc["escalated"] = True
                    self.s.decide(ctx.now, ctx.wf, "alert",
                                  f"incident {inc['id']}: no validated fix available (tried {inc['tried']}); "
                                  f"needs a human", {"severity": "page", "credits": credits}, ref=inc["id"])
        if inc["phase"] == "verifying":
            self._verify(ctx, inc, base)
        st["open"] = inc if inc["phase"] not in ("resolved", "failed_fix") else None
        if inc["phase"] in ("resolved", "failed_fix"):
            st.setdefault("closed", []).append(inc)
            if inc["phase"] == "failed_fix":
                # the fix did not help: open a fresh incident on the new prompt next tick
                pass
        self.save(ctx.wf, st)
        if inc["phase"] != "proposing":
            return []
        v = inc["validation"]
        rec = self._prompt_record(ctx)
        bad, good = rec.get(inc["bad_prompt"], {}), rec.get(inc["fix"], {})
        vol = daily_volume(ctx)
        halluc_now = inc["evidence"]["rate"]
        halluc_fix = (good.get("flags", 0) + 1) / (good.get("conn", 0) + 100) if good else None
        sup = inc.get("supervisor_change_at")
        summary = (f"Revert prompt {inc['bad_prompt']} -> {inc['fix']}: hallucination flags at "
                   f"{halluc_now:.1%} vs normal {base:.1%}"
                   + (f" (reverses a supervisor change made at {fmt(sup)})" if sup is not None else ""))
        return [Intent(
            source="incident", path=["prompt_version"], value=inc["fix"], urgent=True, auto="never",
            summary=summary,
            rationale=(f"Incident {inc['id']}: {inc['evidence']['flags']} hallucination flags in "
                       f"{inc['evidence']['connected']} connected calls on {inc['bad_prompt']} "
                       f"(p={inc['evidence']['p_value']:.1e} against the normal rate). {inc['fix']} "
                       + (f"ran {good['conn']} connected calls here at a {halluc_fix:.1%} flag rate and " if good else "")
                       + f"passed validation at {v['pass_rate']:.3f} (n={v['n']}, policy minimum {min_pass}). "
                       "After apply we verify flags return to normal and engagement does not drop."),
            dry_run={"method": "production flag rates per prompt in this workflow + validation run",
                     "current": {"prompt": inc["bad_prompt"], "flag_rate": halluc_now, **bad},
                     "candidate": {"prompt": inc["fix"], "flag_rate": halluc_fix, **good},
                     "validation": {k: v[k] for k in ("validation_run_id", "n", "pass_rate")}},
            impact=max(0.9, impact_score(ctx, (halluc_now - base) * vol["conn_per_day"])),
            affected_leads=ctx.active_leads(), evidence={"validation_run_id": v["validation_run_id"]},
            ref=inc["id"])]

    def _verify(self, ctx: WorkflowCtx, inc: dict, base: float):
        lo = inc["applied"] // 60
        r = self.s.q("SELECT COALESCE(SUM(conn),0), COALESCE(SUM(flags),0), COALESCE(SUM(eng),0) FROM agg_qa "
                     "WHERE wf=? AND prompt=? AND day*24+hour>=?", (ctx.wf, inc["fix"], lo))[0]
        c, f, e = r
        if c < 150:
            return
        rate = f / c
        pre = self.s.q("SELECT COALESCE(SUM(conn),0), COALESCE(SUM(eng),0) FROM agg_qa WHERE wf=? AND prompt=? "
                       "AND day*24+hour<?", (ctx.wf, inc["bad_prompt"], lo))[0]
        hist = self.s.q("SELECT COALESCE(SUM(conn),0), COALESCE(SUM(eng),0) FROM agg_qa WHERE wf=? AND prompt=? "
                        "AND day*24+hour<?", (ctx.wf, inc["fix"], inc["opened"] // 60))[0]
        ref = hist if hist[0] >= 300 else pre
        eng_check = compare_arms({"fix": (e, c), "before": (ref[1], ref[0])}, "before") if ref[0] else None
        flags_ok = rate <= 1.5 * base or poisson_sf(f, c * base) > 0.01
        eng_drop = bool(eng_check and eng_check["fix"]["p_beats_incumbent"] < 0.05
                        and eng_check["fix"]["lift"] < -0.05)
        detail = {"connected": c, "flags": f, "flag_rate": round(rate, 4), "baseline": round(base, 4),
                  "engagement_vs_reference": eng_check}
        if flags_ok:
            inc["phase"] = "resolved"
            inc["closed"] = ctx.now
            self.s.decide(ctx.now, ctx.wf, "incident_resolved",
                          f"{inc['id']} resolved: flags on {inc['fix']} at {rate:.1%} (normal {base:.1%}); "
                          f"time to fix {(inc['applied'] - inc['opened']) / 60:.1f}h"
                          + ("; engagement fell, see alert" if eng_drop else "; engagement holding"),
                          detail, ref=inc["id"])
            if eng_drop:
                self.s.decide(ctx.now, ctx.wf, "alert", f"{inc['id']}: fix {inc['fix']} is safe but engagement fell "
                              f"{eng_check['fix']['lift']:.0%}; needs a product decision",
                              {"severity": "ticket", **detail}, ref=inc["id"])
        elif c >= 400:
            inc["phase"] = "failed_fix"
            self.s.decide(ctx.now, ctx.wf, "alert", f"{inc['id']}: fix {inc['fix']} did not bring flags down "
                          f"({rate:.1%}); reopening", {"severity": "page", **detail}, ref=inc["id"])
