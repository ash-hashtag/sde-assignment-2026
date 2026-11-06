"""The controller loop: advance -> ingest -> reconcile -> decide, until the scenario ends.

Restart behaviour: on start we ingest every chunk the simulator has that the store hasn't committed, reconcile
every in-flight proposal against the simulator, then decide at the current minute before advancing again.
Deciding twice at the same minute is harmless: modules are pure functions of the store, and proposal ids are
deterministic.
"""
from __future__ import annotations

import json
import logging
import os
import resource
import time

from .client import SimClient
from .ctx import WorkflowCtx
from .governance import Governance
from .ingest import Ingestor
from .modules import build_modules
from .simtime import Clock, MIN_PER_DAY, fmt
from .store import Store

log = logging.getLogger(__name__)


class Controller:
    def __init__(self, url: str, db_path: str, call_log: bool = True):
        self.c = SimClient(url)
        st = self.c.state()
        self.s = Store(db_path)
        self._check_world(st, db_path)
        self.clock = Clock.from_state(st)
        self.s.meta_set("origin", self.clock.origin.isoformat())
        self.specs = {w["workflow_id"]: w for w in self.c.workflows()}
        with self.s.tx() as db:
            for wid, w in self.specs.items():
                db.execute("INSERT INTO workflows VALUES (?,?,?) ON CONFLICT(wf) DO UPDATE SET spec=excluded.spec",
                           (wid, w["tenant_id"], json.dumps(w)))
        self.ing = Ingestor(self.s, self.c, self.clock, call_log=call_log)
        self.gov = Governance(self.s, self.c)
        self.modules = build_modules(self.s, self.c)
        self.credits_start = self.s.meta_get("credits_start")
        if self.credits_start is None:
            self.credits_start = st["credits_remaining"]
            self.s.meta_set("credits_start", self.credits_start)

    def _check_world(self, st: dict, db_path: str):
        """A store belongs to one simulator world. A fresh world (sim restarted) gets a fresh store."""
        known = self.s.meta_get("scenario")
        last = self.s.meta_get("last_minute")
        if known is None:
            self.s.meta_set("scenario", st["scenario"])
            return
        if known != st["scenario"] or (last is not None and st["sim_minute"] < last):
            self.s.close()
            stamp = int(time.time())
            for suffix in ("", "-wal", "-shm"):
                if os.path.exists(db_path + suffix):
                    os.rename(db_path + suffix, f"{db_path}.old-{stamp}{suffix}")
            log.warning("store belonged to another world (%s @ %s); archived it and starting fresh", known, last)
            self.s = Store(db_path)
            self.s.meta_set("scenario", st["scenario"])
        else:
            log.info("resuming %s from %s", known, fmt(last) if last is not None else "start")

    # ------------------------------------------------------------------ main loop
    def run(self):
        t0 = time.time()
        n, secs, notable = self.ing.ingest_all()
        log.info("caught up: %d events in %.1fs", n, secs)
        self._on_events(notable)
        st = self.c.state()
        while True:
            self._tick(st, n, secs)
            if st["finished"]:
                break
            step = self._step(st["sim_minute"], st["end_minute"])
            r = self.c.post("/sim/advance", {"minutes": step})
            if r.status == 409:
                st = self.c.state()
                continue
            self.c.must(r)
            n, secs, notable = self.ing.ingest_all()
            self._on_events(notable)
            st = self.c.state()
        log.info("scenario finished in %.0fs wall", time.time() - t0)

    def _on_events(self, notable: list[dict]):
        for ev in notable:
            if ev["type"] == "config_changed" and ev["actor"] == "supervisor":
                wf = ev["workflow_id"]
                with self.s.tx():
                    dims = self.s.state_get("supervisor", wf, {})
                    for d in ev["changed_dims"]:
                        dims[d] = ev["minute"]
                    self.s.state_set("supervisor", wf, dims)
                    self.s.decide(ev["minute"], wf, "supervisor_edit",
                                  f"supervisor changed {', '.join(ev['changed_dims'])} (v{ev['version']}); "
                                  f"respecting it: no proposals on these dims for a while",
                                  {"event": ev})
            for m in self.modules:
                m.on_event(ev)

    def _ctx(self, wid: str, now: int, end: int | None = None) -> WorkflowCtx:
        cur = self.c.config(wid)
        v = cur["version"]
        if not self.s.q1("SELECT config FROM config_versions WHERE wf=? AND version=?", (wid, v)):
            self.s.db.execute(
                "INSERT INTO config_versions (wf, version, actor, config) VALUES (?,?,?,?) "
                "ON CONFLICT(wf, version) DO UPDATE SET config=excluded.config", (wid, v, cur["actor"],
                                                                                 json.dumps(cur["config"])))
        return WorkflowCtx(wf=wid, spec=self.specs[wid], config=cur["config"], version=v, now=now, store=self.s,
                           supervisor_dims=self.s.state_get("supervisor", wid, {}), end=end)

    def _tick(self, st: dict, n_events: int, ingest_sec: float):
        t0 = time.time()
        now = st["sim_minute"]
        credits = st["credits_remaining"]
        before = self.s.q1("SELECT COUNT(*) FROM proposals")
        for wid in sorted(self.specs):
            ctx = self._ctx(wid, now, st.get("end_minute"))
            self.gov.reconcile(ctx)
            intents = []
            for m in self.modules:
                try:
                    intents += m.intents(ctx, credits=credits, credits_start=self.credits_start)
                except Exception:
                    log.exception("module %s failed on %s", m.name, wid)
                    self.s.decide(now, wid, "alert", f"module {m.name} crashed; workflow left unchanged",
                                  {"severity": "page"})
            if intents:
                self.gov.act(ctx, intents)
        decide = time.time() - t0
        self.s.meta_set("last_minute", now)
        after = self.s.q1("SELECT COUNT(*) FROM proposals")
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        self.s.db.execute("INSERT OR REPLACE INTO metrics VALUES (?,?,?,?,?,?,?,?,?,?)",
                          (now, time.time(), n_events, ingest_sec, decide, ingest_sec + decide, credits,
                           after - before, 0, rss))
        if now % 360 == 0:
            log.info("%s events=%d ingest=%.2fs decide=%.2fs credits=%.0f rss=%.0fMB", fmt(now), n_events,
                     ingest_sec, decide, credits, rss)

    def _step(self, now: int, end: int) -> int:
        """15-minute ticks while anything can happen (dialling or approvers working); otherwise jump ahead."""
        def active(m: int) -> bool:
            h = (m % MIN_PER_DAY) / 60
            for w in self.specs.values():
                lo, hi = w["dialling_window"]
                alo, ahi = w["governance"]["approver_hours"]
                b = w["daily_batch"]["at_hour"]
                if lo - 1 <= h < hi + 0.25 or alo <= h < ahi or b <= h < b + 0.25:
                    return True
            return False
        if active(now):
            return 15
        m = now + 15
        while m < end and not active(m):
            m += 15
        return max(15, min(m, end) - now)
