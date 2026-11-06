"""Checks a finished run for the crash-safety properties: no double apply, no lost approval, nothing ingested twice.

Test-harness only: reads the simulator's run dir to cross-check the controller's own store.
    python scripts/verify_run.py runs/<run> state/<db> http://127.0.0.1:PORT
"""
import json
import sqlite3
import sys
from collections import Counter

import httpx

run, db, url = sys.argv[1:4]
log = [json.loads(l) for l in open(f"{run}/sim_log.jsonl")]
s = sqlite3.connect(db)
c = httpx.Client(base_url=url)
ok = True


def check(name, cond, detail=""):
    global ok
    ok &= bool(cond)
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


state = c.get("/sim/state").json()
check("scenario finished", state["finished"], state["ts"])
applied = Counter(r["approval_id"] for r in log if r["kind"] == "approval_applied")
check("no approval applied twice", all(v == 1 for v in applied.values()), f"{len(applied)} applied")
auto = Counter(r["proposal_id"] for r in log if r["kind"] == "auto_applied")
check("no auto-apply sent twice", all(v == 1 for v in auto.values()), f"{len(auto)} auto-applied")
remote = {a["approval_id"]: a for a in c.get("/approvals").json()}
ours = dict(s.execute("SELECT approval_id, status FROM proposals WHERE approval_id IS NOT NULL").fetchall())
check("every simulator approval is known to the store", set(remote) <= set(ours),
      f"missing: {sorted(set(remote) - set(ours))}")
mismatch = {a: (r["status"], ours.get(a)) for a, r in remote.items()
            if r["status"] in ("applied", "rejected", "expired") and ours.get(a) != r["status"]}
check("store agrees with simulator on decided approvals", not mismatch, str(mismatch))
lost = [a for a, r in remote.items() if r["status"] == "lapsed" and ours.get(a) not in ("lapsed", "deferred")]
check("no approval lapsed unintentionally", not lost, str(lost))
sim_chunks = {ch["chunk"] for k in ("history", "events") for ch in c.get("/events/chunks", params={"kind": k}).json()}
ing = {r[0] for r in s.execute("SELECT n FROM chunks")}
check("every chunk ingested exactly once", sim_chunks == ing, f"{len(ing)}/{len(sim_chunks)}")
calls_sim = state["last_event_id"]
calls_db = s.execute("SELECT SUM(events) FROM chunks").fetchone()[0]
check("event count matches", calls_sim == calls_db, f"{calls_db}/{calls_sim}")
dials = s.execute("SELECT SUM(dials) FROM agg_pick").fetchone()[0]
n_calls = sum(1 for k in ("history", "events") for ch in c.get("/events/chunks", params={"kind": k}).json()
              for line in c.get(f"/events/chunks/{ch['chunk']}").text.splitlines() if '"type":"call"' in line)
check("aggregates count every call once", dials == n_calls, f"{dials}/{n_calls}")
sys.exit(0 if ok else 1)
