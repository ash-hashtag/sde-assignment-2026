"""SQLite store: the controller's only state.

Everything the controller knows lives here, so a restart is "open the file and carry on". Ingestion writes one
transaction per event chunk (aggregates and the chunk marker together), so a chunk is either fully counted or
not at all. Decisions, proposals and their outcomes are append-mostly tables that double as the audit trail.

The schema avoids SQLite-only features apart from upserts, so it ports to the Postgres SRE already runs.
"""
from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);

CREATE TABLE IF NOT EXISTS chunks (
  n INTEGER PRIMARY KEY, kind TEXT, events INTEGER, last_event_id INTEGER, until_minute INTEGER,
  ingested_wall REAL, ingest_sec REAL);

CREATE TABLE IF NOT EXISTS workflows (wf TEXT PRIMARY KEY, tenant TEXT, spec TEXT);

CREATE TABLE IF NOT EXISTS atoms (
  id INTEGER PRIMARY KEY, lang TEXT, city_tier TEXT, age_band TEXT, value_band TEXT,
  UNIQUE (lang, city_tier, age_band, value_band));

CREATE TABLE IF NOT EXISTS persons (pid TEXT PRIMARY KEY, wf TEXT, atom INTEGER);

CREATE TABLE IF NOT EXISTS campaigns (
  campaign_id TEXT PRIMARY KEY, wf TEXT, day INTEGER, leads INTEGER, config_version INTEGER,
  concluded INTEGER DEFAULT 0);

-- pickup: who was dialled when, from which caller ID, on which day of their campaign (fresh leads pick up more
-- than retries, and on next_campaign_only workflows a new caller ID only reaches fresh campaigns at first)
CREATE TABLE IF NOT EXISTS agg_pick (
  wf TEXT, day INTEGER, hour INTEGER, atom INTEGER, did TEXT, cday INTEGER, dials INTEGER, conn INTEGER,
  PRIMARY KEY (wf, day, hour, atom, did, cday));

-- engagement: connected calls by the variant they actually ran with
CREATE TABLE IF NOT EXISTS agg_eng (
  wf TEXT, day INTEGER, hour INTEGER, atom INTEGER, wm TEXT, voice TEXT, prompt TEXT, conn INTEGER, eng INTEGER,
  PRIMARY KEY (wf, day, hour, atom, wm, voice, prompt));

-- quality: hallucination flags by prompt
CREATE TABLE IF NOT EXISTS agg_qa (
  wf TEXT, day INTEGER, hour INTEGER, prompt TEXT, conn INTEGER, flags INTEGER, eng INTEGER,
  PRIMARY KEY (wf, day, hour, prompt));

-- per-call record for "why did this customer hear this" (controller era only, not history)
CREATE TABLE IF NOT EXISTS call_log (
  event_id INTEGER PRIMARY KEY, wf TEXT, minute INTEGER, lead_id TEXT, person_id TEXT, attempt INTEGER,
  config_version INTEGER, cohort TEXT, wm TEXT, voice TEXT, did TEXT, prompt TEXT, connected INTEGER,
  engaged INTEGER);
CREATE INDEX IF NOT EXISTS call_log_lead ON call_log (lead_id);
CREATE INDEX IF NOT EXISTS call_log_person ON call_log (person_id);

CREATE TABLE IF NOT EXISTS config_versions (
  wf TEXT, version INTEGER, actor TEXT, changed_dims TEXT, applied_minute INTEGER, proposal_id TEXT,
  approval_id TEXT, config TEXT, PRIMARY KEY (wf, version));

CREATE TABLE IF NOT EXISTS sim_events (
  event_id INTEGER PRIMARY KEY, type TEXT, wf TEXT, minute INTEGER, body TEXT);

CREATE TABLE IF NOT EXISTS proposals (
  proposal_id TEXT PRIMARY KEY, wf TEXT, path TEXT, status TEXT, urgent INTEGER, base_version INTEGER,
  dims TEXT, intents TEXT, request TEXT, config TEXT, approval_id TEXT, created_minute INTEGER,
  decided_minute INTEGER, applied_minute INTEGER, applied_version INTEGER, reasons TEXT, outcome TEXT);
CREATE INDEX IF NOT EXISTS proposals_wf ON proposals (wf, status);

CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, minute INTEGER, wf TEXT, kind TEXT, ref TEXT, summary TEXT,
  detail TEXT);
CREATE INDEX IF NOT EXISTS decisions_wf ON decisions (wf, minute);

CREATE TABLE IF NOT EXISTS state (module TEXT, key TEXT, value TEXT, PRIMARY KEY (module, key));

CREATE TABLE IF NOT EXISTS metrics (
  minute INTEGER PRIMARY KEY, wall REAL, events INTEGER, ingest_sec REAL, decide_sec REAL, loop_sec REAL,
  credits REAL, proposals INTEGER, auto_applies INTEGER, rss_mb REAL);
"""


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, isolation_level=None)  # explicit transactions only
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.execute("PRAGMA temp_store=MEMORY")
        self.db.executescript(SCHEMA)
        self._in_tx = False

    @contextmanager
    def tx(self):
        """One atomic unit of work. Nested use joins the outer transaction."""
        if self._in_tx:
            yield self.db
            return
        self.db.execute("BEGIN IMMEDIATE")
        self._in_tx = True
        try:
            yield self.db
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        else:
            self.db.execute("COMMIT")
        finally:
            self._in_tx = False

    def q(self, sql: str, args=()) -> list[tuple]:
        return self.db.execute(sql, args).fetchall()

    def q1(self, sql: str, args=()):
        r = self.db.execute(sql, args).fetchone()
        return r[0] if r else None

    # -- small key/value helpers
    def meta_get(self, key: str, default=None):
        v = self.q1("SELECT value FROM meta WHERE key=?", (key,))
        return default if v is None else json.loads(v)

    def meta_set(self, key: str, value):
        self.db.execute("INSERT INTO meta VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                        (key, json.dumps(value)))

    def state_get(self, module: str, key: str, default=None):
        v = self.q1("SELECT value FROM state WHERE module=? AND key=?", (module, key))
        return default if v is None else json.loads(v)

    def state_set(self, module: str, key: str, value):
        self.db.execute("INSERT INTO state VALUES (?,?,?) ON CONFLICT(module,key) DO UPDATE SET value=excluded.value",
                        (module, key, json.dumps(value, sort_keys=True)))

    def state_all(self, module: str) -> dict:
        return {k: json.loads(v) for k, v in self.q("SELECT key, value FROM state WHERE module=?", (module,))}

    def decide(self, minute: int, wf: str | None, kind: str, summary: str, detail: dict | None = None,
               ref: str | None = None) -> int:
        """Appends one record to the audit trail and returns its id."""
        cur = self.db.execute("INSERT INTO decisions (minute, wf, kind, ref, summary, detail) VALUES (?,?,?,?,?,?)",
                              (minute, wf, kind, ref, summary, json.dumps(detail or {}, sort_keys=True,
                                                                         default=str)))
        return cur.lastrowid

    def close(self):
        self.db.close()


def now_wall() -> float:
    return time.time()
