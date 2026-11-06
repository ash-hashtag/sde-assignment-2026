"""Event ingestion: chunk -> aggregates, exactly once.

A chunk is counted inside a single transaction together with its row in `chunks`, so re-running ingestion after a
crash skips what was committed and redoes what wasn't. Aggregation happens in memory per chunk and lands as a
batch of upserts, which keeps the load scenario (~850k events/day) to a few seconds of CPU per simulated day.
"""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict

from .client import SimClient
from .simtime import Clock, MIN_PER_DAY
from .store import Store

log = logging.getLogger(__name__)

FEATURES = ("lang", "city_tier", "age_band", "value_band")


class Ingestor:
    def __init__(self, store: Store, client: SimClient, clock: Clock, call_log: bool = True):
        self.s, self.c, self.clock = store, client, clock
        self.call_log = call_log
        self.atoms: dict[tuple, int] = {tuple(r[1:]): r[0] for r in store.q(
            "SELECT id, lang, city_tier, age_band, value_band FROM atoms")}
        t0 = time.time()
        self.person_atom: dict[str, int] = dict(store.q("SELECT pid, atom FROM persons"))
        if self.person_atom:
            log.info("loaded %d persons in %.1fs", len(self.person_atom), time.time() - t0)

    def last_chunk(self) -> int:
        return self.s.q1("SELECT COALESCE(MAX(n), -1) FROM chunks")

    def pending(self) -> list[dict]:
        """Chunks the simulator has that we haven't committed, history first, in chunk order."""
        done = {r[0] for r in self.s.q("SELECT n FROM chunks")}
        out = []
        for kind in ("history", "events"):
            out += [c for c in self.c.chunks(kind, -1) if c["chunk"] not in done]
        return sorted(out, key=lambda c: c["chunk"])

    def ingest_all(self) -> tuple[int, float, list[dict]]:
        n_events, secs, notable = 0, 0.0, []
        for meta in self.pending():
            k, dt_, nb = self.ingest_chunk(meta)
            n_events += k
            secs += dt_
            notable += nb
        return n_events, secs, notable

    def _atom(self, feats: dict) -> int:
        key = tuple(feats[f] for f in FEATURES)
        a = self.atoms.get(key)
        if a is None:
            a = len(self.atoms) + 1
            self.atoms[key] = a
            self._new_atoms.append((a, *key))
        return a

    def ingest_chunk(self, meta: dict) -> tuple[int, float, list[dict]]:
        try:
            return self._ingest_chunk(meta)
        except BaseException:
            # the in-memory join caches may now be ahead of the rolled-back DB; rebuild them from the DB
            self.__init__(self.s, self.c, self.clock, self.call_log)
            raise

    def _ingest_chunk(self, meta: dict) -> tuple[int, float, list[dict]]:
        t0 = time.time()
        n = meta["chunk"]
        self._new_atoms: list[tuple] = []
        new_persons: list[tuple] = []
        campaigns: list[tuple] = []
        concluded: dict[str, int] = defaultdict(int)
        pick: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
        eng: dict[tuple, list[int]] = defaultdict(lambda: [0, 0])
        qa: dict[tuple, list[int]] = defaultdict(lambda: [0, 0, 0])
        calls: list[tuple] = []
        sim_events: list[tuple] = []
        versions: list[tuple] = []
        notable: list[dict] = []
        minute_of = self.clock.minute
        pa = self.person_atom
        count = 0
        for ev in self.c.chunk_events(n):
            count += 1
            t = ev["type"]
            if t == "call":
                m = minute_of(ev["ts"])
                day, hour = divmod(m, MIN_PER_DAY)
                hour //= 60
                wf = ev["workflow_id"]
                atom = pa.get(ev["person_id"], 0)
                v = ev["variant"]
                conn = ev["connected"]
                p = pick[(wf, day, hour, atom, v["caller_id"])]
                p[0] += 1
                if conn:
                    p[1] += 1
                    e = ev["engaged"]
                    g = eng[(wf, day, hour, atom, v["welcome_message"], v["voice"], v["prompt_version"])]
                    g[0] += 1
                    g[1] += e
                    q = qa[(wf, day, hour, v["prompt_version"])]
                    q[0] += 1
                    q[1] += bool(ev["qa"] and ev["qa"]["hallucination_flag"])
                    q[2] += e
                    if e:
                        concluded[ev["campaign_id"]] += 1
                if self.call_log and m >= 0:
                    calls.append((ev["event_id"], wf, m, ev["lead_id"], ev["person_id"], ev["attempt_no"],
                                  ev["config_version"], ev["cohort_id"], v["welcome_message"], v["voice"],
                                  v["caller_id"], v["prompt_version"], int(conn), int(ev["engaged"])))
            elif t == "lead":
                pid = ev["person_id"]
                if pid not in pa:
                    a = self._atom(ev["features"])
                    pa[pid] = a
                    new_persons.append((pid, ev["workflow_id"], a))
            elif t == "campaign_created":
                m = minute_of(ev["ts"])
                campaigns.append((ev["campaign_id"], ev["workflow_id"], m // MIN_PER_DAY, ev["leads"],
                                  ev["config_version_at_creation"]))
            else:
                m = minute_of(ev["ts"])
                sim_events.append((ev["event_id"], t, ev.get("workflow_id"), m, json.dumps(ev)))
                if t == "config_changed":
                    versions.append((ev["workflow_id"], ev["version"], ev["actor"], json.dumps(ev["changed_dims"]),
                                     m, ev.get("proposal_id"), ev.get("approval_id")))
                notable.append({**ev, "minute": m})

        with self.s.tx() as db:
            if db.execute("SELECT 1 FROM chunks WHERE n=?", (n,)).fetchone():
                return 0, 0.0, []  # another run of us got here first
            db.executemany("INSERT INTO atoms VALUES (?,?,?,?,?)", self._new_atoms)
            db.executemany("INSERT OR IGNORE INTO persons VALUES (?,?,?)", new_persons)
            db.executemany("INSERT OR IGNORE INTO campaigns (campaign_id, wf, day, leads, config_version) "
                           "VALUES (?,?,?,?,?)", campaigns)
            db.executemany("UPDATE campaigns SET concluded = concluded + ? WHERE campaign_id = ?",
                           [(k, cid) for cid, k in concluded.items()])
            db.executemany("INSERT INTO agg_pick VALUES (?,?,?,?,?,?,?) ON CONFLICT DO UPDATE SET "
                           "dials = dials + excluded.dials, conn = conn + excluded.conn",
                           [(*k, v[0], v[1]) for k, v in pick.items()])
            db.executemany("INSERT INTO agg_eng VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT DO UPDATE SET "
                           "conn = conn + excluded.conn, eng = eng + excluded.eng",
                           [(*k, v[0], v[1]) for k, v in eng.items()])
            db.executemany("INSERT INTO agg_qa VALUES (?,?,?,?,?,?,?) ON CONFLICT DO UPDATE SET "
                           "conn = conn + excluded.conn, flags = flags + excluded.flags, eng = eng + excluded.eng",
                           [(*k, *v) for k, v in qa.items()])
            db.executemany("INSERT OR IGNORE INTO call_log VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", calls)
            db.executemany("INSERT OR IGNORE INTO sim_events VALUES (?,?,?,?,?)", sim_events)
            db.executemany("INSERT INTO config_versions (wf, version, actor, changed_dims, applied_minute, "
                           "proposal_id, approval_id) VALUES (?,?,?,?,?,?,?) ON CONFLICT DO NOTHING", versions)
            secs = time.time() - t0
            db.execute("INSERT INTO chunks VALUES (?,?,?,?,?,?,?)",
                       (n, meta["kind"], count, meta["last_event_id"], meta["until_minute"], time.time(), secs))
        return count, secs, notable
