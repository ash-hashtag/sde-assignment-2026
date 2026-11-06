"""Governance client: turns intents into config changes without ever crossing the boundary.

Lifecycle of one proposal (table `proposals`):

    submitting ──POST ok──> pending ──> approved ──apply ok──> applied
        │                     │           │  ├──409 stale──> stale      (re-proposed from fresh intents)
        │                     │           │  ├──410────────> lapsed
        │                     │           │  └──urgent in flight──> deferred (left to lapse, re-proposed later)
        │                     │           └──(not applied in window)──> lapsed
        │                     ├──> rejected  (reasons recorded; intents come back next slot with fresh data)
        │                     └──> expired   (treated as a rejection; never resubmitted as-is)
        ├──4xx──> refused
        └──crash before response──> reconciled on restart from GET /approvals / config history

Auto-apply proposals go submitting -> applied | refused.

Every row is written *before* the HTTP call with a deterministic proposal_id, so a crash at any point either
finds the proposal in the simulator on restart or knows it never got there. Applying is guarded by the
approval's own status, so it can't happen twice.

Freeze rule: while an approval is in flight for a workflow, non-urgent auto-applies wait, because any
config change bumps the version and would make the pending approval stale.
"""
from __future__ import annotations

import hashlib
import json
import logging

from . import settings as S
from .client import SimClient
from .ctx import WorkflowCtx
from .intents import (Intent, apply_intents, blend, changed_dims, dist_for, get_path, max_shift, same_value)
from .simtime import MIN_PER_DAY, fmt
from .store import Store

log = logging.getLogger(__name__)

IN_FLIGHT = ("submitting", "pending", "approved", "applying")


class Governance:
    def __init__(self, store: Store, client: SimClient):
        self.s, self.c = store, client

    # ------------------------------------------------------------------ reconciliation
    def reconcile(self, ctx: WorkflowCtx):
        """Brings our proposal rows in line with the simulator. Safe to call any time, including after a crash."""
        rows = self.s.q("SELECT proposal_id, path, status, approval_id, urgent FROM proposals "
                        "WHERE wf=? AND status IN ('submitting','pending','approved','applying')", (ctx.wf,))
        if not rows:
            return
        remote = {a["proposal_id"]: a for a in self.c.must(self.c.get("/approvals", workflow_id=ctx.wf))}
        history = None
        for pid, path, status, aid, urgent in rows:
            if path == "auto":
                if history is None:
                    history = {v["proposal_id"]: v for v in self.c.config_history(ctx.wf) if v["proposal_id"]}
                v = history.get(pid)
                with self.s.tx():
                    if v:
                        self._set(pid, status="applied", applied_version=v["version"], applied_minute=ctx.now)
                        self.s.decide(ctx.now, ctx.wf, "auto_applied", f"auto-apply {pid} confirmed after restart",
                                      {"version": v["version"]}, ref=pid)
                    else:
                        self._set(pid, status="abandoned", outcome="never reached the simulator")
                continue
            a = remote.get(pid)
            if a is None:
                if status == "submitting":
                    self._set(pid, status="abandoned", outcome="never reached the simulator")
                continue
            if aid is None:
                self._set(pid, approval_id=a["approval_id"])
            self._on_remote(ctx, pid, a, bool(urgent))

    def _on_remote(self, ctx: WorkflowCtx, pid: str, a: dict, urgent: bool):
        st = a["status"]
        cur = self.s.q1("SELECT status FROM proposals WHERE proposal_id=?", (pid,))
        if st == "pending":
            if cur == "submitting":
                self._set(pid, status="pending")
            return
        if st in ("rejected", "expired", "lapsed"):
            with self.s.tx():
                self._set(pid, status=st, reasons=json.dumps(a.get("reasons") or []),
                          decided_minute=ctx.now)
                self.s.decide(ctx.now, ctx.wf, f"approval_{st}",
                              f"{a['approval_id']} {st}" + (f": {'; '.join(a['reasons'])}" if a.get("reasons") else ""),
                              {"approval": a}, ref=pid)
            return
        if st == "applied":
            if cur != "applied":
                with self.s.tx():
                    v = self._version_for_approval(ctx.wf, a["approval_id"])
                    self._set(pid, status="applied", applied_version=v, applied_minute=ctx.now)
                    self.s.decide(ctx.now, ctx.wf, "applied", f"{a['approval_id']} applied as v{v} (reconciled)",
                                  {"approval": a}, ref=pid)
            return
        if st == "approved":
            if cur in ("submitting", "pending"):
                with self.s.tx():
                    self._set(pid, status="approved", decided_minute=ctx.now)
                    self.s.decide(ctx.now, ctx.wf, "approval_approved", f"{a['approval_id']} approved",
                                  {"approval": a}, ref=pid)
            self._apply(ctx, pid, a, urgent)

    def _apply(self, ctx: WorkflowCtx, pid: str, a: dict, urgent: bool):
        if not urgent:
            other = self.s.q1("SELECT proposal_id FROM proposals WHERE wf=? AND urgent=1 AND proposal_id<>? AND "
                              "status IN ('submitting','pending','approved')", (ctx.wf, pid))
            if other:
                with self.s.tx():
                    self._set(pid, status="deferred", outcome=f"urgent proposal {other} in flight")
                    self.s.decide(ctx.now, ctx.wf, "apply_deferred",
                                  f"not applying {a['approval_id']}: incident fix {other} is in flight and would go stale",
                                  ref=pid)
                return
        self._set(pid, status="applying")
        r = self.c.post(f"/workflows/{ctx.wf}/apply", {"approval_id": a["approval_id"]})
        with self.s.tx():
            if r.ok:
                v = r.body["version"]
                self._set(pid, status="applied", applied_version=v, applied_minute=ctx.now)
                self.s.decide(ctx.now, ctx.wf, "applied", f"{a['approval_id']} applied as v{v}",
                              {"changed_dims": r.body.get("changed_dims")}, ref=pid)
                ctx.version = v
                ctx.config = self.c.config(ctx.wf)["config"]
            elif r.code == "approval_lapsed":
                self._set(pid, status="lapsed", outcome="apply window passed")
                self.s.decide(ctx.now, ctx.wf, "approval_lapsed", f"{a['approval_id']} lapsed before apply", ref=pid)
            elif r.code == "stale_base_version":
                self._set(pid, status="stale", outcome=json.dumps(r.body))
                self.s.decide(ctx.now, ctx.wf, "apply_stale",
                              f"{a['approval_id']} approved but config moved on (now v{r.body['detail']['current_version']});"
                              f" intents will be re-proposed on the new base", {"response": r.body}, ref=pid)
            elif r.code == "not_approved":
                self._set(pid, status=r.body["detail"]["status"])
            else:
                self._set(pid, status="refused", outcome=json.dumps(r.body))
                self.s.decide(ctx.now, ctx.wf, "alert", f"apply of {a['approval_id']} failed: {r.body}",
                              {"severity": "page"}, ref=pid)

    def _version_for_approval(self, wf: str, aid: str):
        for v in self.c.config_history(wf):
            if v["approval_id"] == aid:
                return v["version"]
        return None

    def _set(self, pid: str, **cols):
        sets = ", ".join(f"{k}=?" for k in cols)
        self.s.db.execute(f"UPDATE proposals SET {sets} WHERE proposal_id=?", (*cols.values(), pid))

    # ------------------------------------------------------------------ acting on intents
    def act(self, ctx: WorkflowCtx, intents: list[Intent]):
        intents = [it for it in intents if not same_value(get_path(ctx.config, it.path), it.value)]
        if not intents:
            return
        in_flight = self._in_flight(ctx.wf)
        # auto path
        auto = [it for it in intents if it.auto != "never" and ctx.auto_allowed(it.dim)]
        frozen = any(r["path"] == "approval" for r in in_flight)
        auto_now = [it for it in auto if it.urgent or not frozen]
        done = self._auto_apply(ctx, auto_now) if auto_now else []
        # approval path: whatever auto-apply could not do, or is waiting on a freeze
        rest = [it for it in intents if not any(it is d for d in done)]
        rest = [it for it in rest if not self._covered(it, self._in_flight(ctx.wf))]
        if not rest or all(it.piggyback for it in rest):
            return
        urgent = [it for it in rest if it.urgent]
        if urgent:
            self._request(ctx, urgent, urgent=True)
        elif not any(r["path"] == "approval" for r in in_flight):
            self._request(ctx, rest, urgent=False)

    def _in_flight(self, wf: str) -> list[dict]:
        rows = self.s.q("SELECT proposal_id, path, intents, urgent FROM proposals WHERE wf=? AND status IN "
                        "('submitting','pending','approved','applying')", (wf,))
        return [{"proposal_id": r[0], "path": r[1], "intents": json.loads(r[2]), "urgent": r[3]} for r in rows]

    @staticmethod
    def _covered(it: Intent, in_flight: list[dict]) -> bool:
        return any(i["path"] == it.path and same_value(i["value"], it.value)
                   for r in in_flight for i in r["intents"])

    def _proposal_id(self, ctx: WorkflowCtx, kind: str, cfg: dict) -> str:
        """Deterministic, so a restart within the same tick regenerates the same id and the simulator's
        duplicate check backs up our own reconciliation. Abandoned ids (never reached the simulator) get a suffix."""
        h = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:8]
        base = f"{ctx.wf}-{kind}-{ctx.now}-v{ctx.version}-{h}"
        n = self.s.q1("SELECT COUNT(*) FROM proposals WHERE proposal_id = ? OR proposal_id LIKE ?", (base, base + "-r%"))
        return base if not n else f"{base}-r{n}"

    # -- auto
    def _auto_apply(self, ctx: WorkflowCtx, intents: list[Intent]) -> list[Intent]:
        new = apply_intents(ctx.config, intents)
        limit = float((ctx.gov.get("auto_apply") or {}).get("max_shift", 0))
        shift = max_shift(ctx.config, new)
        stepped = False
        if shift > limit + 1e-9:
            if not all(it.step_ok for it in intents if it.path[0] == "allocations"):
                # too big a move for auto-apply: allocation changes go to a human, the rest can still auto-apply
                others = [it for it in intents if it.path[0] != "allocations"]
                return self._auto_apply(ctx, others) if others else []
            alpha = limit / shift * 0.999
            for it in intents:
                if it.path[0] == "allocations":
                    old = dist_for(ctx.config, it.path[1], it.path[2])
                    it_new = blend(old, it.value, alpha)
                    new.setdefault("allocations", {}).setdefault(it.path[1], {})[it.path[2]] = it_new
            stepped = True
        dims = changed_dims(ctx.config, new)
        if not dims:
            return []
        pid = self._proposal_id(ctx, "auto", new)
        rationale = " | ".join(it.rationale for it in intents)
        evidence = {"intents": [it.to_json() for it in intents], "stepped_within_max_shift": stepped}
        with self.s.tx():
            self.s.db.execute(
                "INSERT INTO proposals (proposal_id, wf, path, status, urgent, base_version, dims, intents, request, "
                "config, created_minute) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (pid, ctx.wf, "auto", "submitting", int(any(i.urgent for i in intents)), ctx.version, json.dumps(dims),
                 json.dumps([i.to_json() for i in intents]), json.dumps({"rationale": rationale}),
                 json.dumps(new), ctx.now))
        r = self.c.put(f"/workflows/{ctx.wf}/config", {"proposal_id": pid, "base_version": ctx.version,
                                                       "proposed_config": new, "rationale": rationale,
                                                       "evidence": evidence})
        with self.s.tx():
            if r.ok:
                v = r.body["version"]
                self._set(pid, status="applied", applied_version=v, applied_minute=ctx.now)
                self.s.decide(ctx.now, ctx.wf, "auto_applied",
                              f"v{v}: " + "; ".join(it.summary for it in intents) + (" (stepped)" if stepped else ""),
                              {"dims": dims, "intents": [it.to_json() for it in intents]}, ref=pid)
                ctx.version = v
                ctx.config = self.c.config(ctx.wf)["config"]
                return intents
            self._set(pid, status="refused", outcome=json.dumps(r.body))
            self.s.decide(ctx.now, ctx.wf, "auto_apply_refused", f"auto-apply refused: {r.body}",
                          {"severity": "ticket", "response": r.body}, ref=pid)
            return []

    # -- approval
    def quota(self, ctx: WorkflowCtx) -> tuple[int, int]:
        """(requests made in the last 24h, voluntary+policy limit)."""
        used = self.s.q1("SELECT COUNT(*) FROM proposals WHERE wf=? AND path='approval' AND approval_id IS NOT NULL "
                         "AND created_minute > ?", (ctx.wf, ctx.now - MIN_PER_DAY))
        limit = ctx.gov["max_requests_per_24h"]
        pref = S.TENANT_PREFS.get(ctx.tenant, {})
        limit = min(limit, pref.get("max_requests_per_day", limit))
        return used, limit

    def can_request_now(self, ctx: WorkflowCtx, urgent: bool) -> tuple[bool, str]:
        lo, hi = ctx.gov["approver_hours"]
        pref = S.TENANT_PREFS.get(ctx.tenant, {})
        start = max(lo, pref.get("earliest_request_hour", lo)) if not urgent else lo
        m = ctx.now % MIN_PER_DAY
        if not (start * 60 <= m < hi * 60):
            return False, "outside approver hours"
        lat_max = ctx.gov["approver_latency_minutes"][1]
        ttl_min = ctx.gov["proposal_ttl_hours"] * 60
        same_day = m + lat_max <= hi * 60
        next_open_ok = (MIN_PER_DAY - m + lo * 60) <= ttl_min
        if not (same_day or next_open_ok):
            return False, "a decision could land after expiry"
        used, limit = self.quota(ctx)
        allowed = limit if urgent else max(limit - S.RESERVED_URGENT_SLOTS, 1 if limit >= 1 else 0)
        if used >= allowed:
            return False, f"quota {used}/{limit} (reserve kept for incidents)"
        if not urgent:
            last = self.s.q1("SELECT MAX(created_minute) FROM proposals WHERE wf=? AND path='approval' "
                             "AND approval_id IS NOT NULL", (ctx.wf,))
            if last is not None and ctx.now - last < S.MIN_HOURS_BETWEEN_REQUESTS * 60:
                return False, "spacing between requests"
        return True, ""

    def _request(self, ctx: WorkflowCtx, intents: list[Intent], urgent: bool):
        ok, why = self.can_request_now(ctx, urgent)
        if not ok:
            return
        new = apply_intents(ctx.config, intents)
        dims = changed_dims(ctx.config, new)
        if not dims:
            return
        pid = self._proposal_id(ctx, "urgent" if urgent else "req", new)
        diff = {it.key: {"from": get_path(ctx.config, it.path), "to": it.value} for it in intents}
        impact = 1.0
        for it in intents:
            impact *= 1 - max(0.0, min(1.0, it.impact))
        evidence = {}
        for it in intents:
            evidence.update(it.evidence)
        body = {
            "proposal_id": pid, "workflow_id": ctx.wf, "base_version": ctx.version, "proposed_config": new,
            "change_summary": "; ".join(it.summary for it in intents),
            "diff": diff,
            "affected_leads": int(max(it.affected_leads for it in intents)),
            "dry_run": {it.key: it.dry_run for it in intents},
            "impact_score": round(1 - impact, 3),
            "rationale": " | ".join(it.rationale for it in intents),
            "evidence": evidence,
            "expires_in_hours": ctx.gov["proposal_ttl_hours"],
        }
        with self.s.tx():
            self.s.db.execute(
                "INSERT INTO proposals (proposal_id, wf, path, status, urgent, base_version, dims, intents, request, "
                "config, created_minute) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (pid, ctx.wf, "approval", "submitting", int(urgent), ctx.version, json.dumps(dims),
                 json.dumps([i.to_json() for i in intents]),
                 json.dumps({k: v for k, v in body.items() if k != "proposed_config"}, default=str),
                 json.dumps(new), ctx.now))
        r = self.c.post("/approvals", body)
        with self.s.tx():
            if r.ok:
                self._set(pid, status="pending", approval_id=r.body["approval_id"])
                self.s.decide(ctx.now, ctx.wf, "approval_requested",
                              f"{r.body['approval_id']} requested at {fmt(ctx.now)}: {body['change_summary']}",
                              {"impact_score": body["impact_score"], "affected_leads": body["affected_leads"],
                               "dims": dims, "urgent": urgent}, ref=pid)
            else:
                self._set(pid, status="refused", outcome=json.dumps(r.body))
                self.s.decide(ctx.now, ctx.wf, "approval_refused", f"approval request refused: {r.body}",
                              {"severity": "ticket", "response": r.body}, ref=pid)
