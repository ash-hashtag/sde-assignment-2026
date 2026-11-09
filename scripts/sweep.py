"""Multi-seed evaluation: one run is one draw of a noisy world, so judge controller changes on several.

For each scenario and seed: rewrite the scenario's seed into a copy under runs/sweep/, run the no-op baseline and
the controller against it, grade, and aggregate. Same truth, different people and dice. Test harness only: it
reads scenario files and simulator run dirs, which the controller itself never does.

    python scripts/sweep.py --label final --seeds 5 [--jobs 6] [--set '{"MAX_CHALLENGER_SHARE": 0.15}'] [scenario.yaml ...]
    -> reports/sweep_<label>.md and runs/sweep/<label>.json
"""
from __future__ import annotations

import argparse
import json
import os
import statistics as st
import subprocess
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
PY = str(ROOT / ".venv/bin/python")
DEFAULT = ["scenarios/public_01_dev.yaml", "scenarios/public_02_incidents.yaml",
           "tests/scenarios/variant_a.yaml", "tests/scenarios/variant_b.yaml"]


def run_one(sc_path: str, seed: int, port: int, label: str, overrides: str = "") -> dict:
    sc = yaml.safe_load((ROOT / sc_path).read_text())
    name = f"{sc['name']}_s{seed}"
    d = ROOT / "runs/sweep" / label / name
    d.mkdir(parents=True, exist_ok=True)
    sc["seed"] = seed
    (d / "scenario.yaml").write_text(yaml.safe_dump(sc, sort_keys=False))
    env = {**os.environ, "PYTHONHASHSEED": "0", "CONTROLLER_SETTINGS": overrides}
    base = ROOT / "runs/sweep/baselines" / name   # baselines don't depend on the controller: share them
    if not (base / "agg.json").exists() and not any(base.glob("*")):
        subprocess.run([PY, "-m", "sim", "baseline", "--scenario", str(d / "scenario.yaml"), "--run-dir", str(base)],
                       cwd=ROOT, check=True, capture_output=True, env=env)
    sim = subprocess.Popen([PY, "-m", "sim", "serve", "--scenario", str(d / "scenario.yaml"), "--run-dir",
                            str(d / "run"), "--force", "--port", str(port)], cwd=ROOT,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    try:
        import httpx
        for _ in range(240):
            try:
                if httpx.get(f"http://127.0.0.1:{port}/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.5)
        db = d / "controller.db"
        for f in (db, Path(f"{db}-wal"), Path(f"{db}-shm")):
            f.unlink(missing_ok=True)
        with open(d / "controller.log", "w") as log:
            subprocess.run([PY, "-m", "controller", "run", "--url", f"http://127.0.0.1:{port}", "--db", str(db)],
                           cwd=ROOT, check=True, stdout=log, stderr=log, env=env)
    finally:
        sim.terminate()
        sim.wait()
    g = json.loads(subprocess.run([PY, "-m", "sim", "grade", "--run", str(d / "run"), "--baseline", str(base),
                                   "--json"], cwd=ROOT, check=True, capture_output=True, text=True).stdout)
    return summarise(sc["name"], seed, g)


def summarise(scenario: str, seed: int, g: dict) -> dict:
    def total(k):
        s = Counter()
        for w in k.values():
            for m in ("leads_uploaded", "leads_concluded", "dials", "connected", "engaged", "hallucinated_calls"):
                s[m] += w[m]
        return s
    a, b = total(g["kpis"]), total(g["baseline_kpis"])
    rate = lambda s, n, d: s[n] / max(s[d], 1)
    harmful = [{"wf": c["workflow_id"], "v": c["version"], "dims": c["dims"], "actor": c["actor"],
                "engage": c["engage_delta"], "did": c["did_health_delta"]}
               for c in g["controller_changes"]["detail"] if c["verdict"] == "harmful"]
    decay_tail = {k: v[max(v, key=int)] for k, v in g["decaying_variant_share_after_onset"].items() if v}
    return {
        "scenario": scenario, "seed": seed,
        "conclusion": rate(a, "leads_concluded", "leads_uploaded") / rate(b, "leads_concluded", "leads_uploaded") - 1,
        "pickup": rate(a, "connected", "dials") / rate(b, "connected", "dials") - 1,
        "engagement": rate(a, "engaged", "connected") / rate(b, "engaged", "connected") - 1,
        "halluc": a["hallucinated_calls"], "halluc_base": b["hallucinated_calls"],
        "changes": g["controller_changes"]["count"], "harmful": harmful,
        "expired": g["governance"]["decisions"].get("expired", 0), "lapsed": g["governance"]["lapsed"],
        "mttr": [i["mttr_minutes"] for i in g["incidents"] if i.get("mttr_minutes") is not None],
        "decay_last_day_share": decay_tail, "credits": g["credits_used"],
    }


def fmt_ms(xs):
    if not xs:
        return "—"
    m = st.mean(xs)
    return f"{m:+.1%} ± {st.stdev(xs):.1%}" if len(xs) > 1 else f"{m:+.1%}"


def report(label: str, rows: list[dict]) -> str:
    out = [f"# Seed sweep — {label}", "",
           "Each scenario re-run with different seeds (same hidden truth, different people and dice). "
           "Mean ± standard deviation across seeds; generated by `scripts/sweep.py`.", "",
           "| scenario | seeds | conclusions Δ | pickup Δ | engagement Δ | harmful / changes | runs with any harmful "
           "| expired+lapsed | incident MTTR (min) | decaying arm still live at end |",
           "|---|---|---|---|---|---|---|---|---|---|"]
    for sc in dict.fromkeys(r["scenario"] for r in rows):
        rs = [r for r in rows if r["scenario"] == sc]
        mttr = [m for r in rs for m in r["mttr"]]
        tails = [s for r in rs for s in r["decay_last_day_share"].values()]
        out.append(
            f"| {sc} | {len(rs)} | {fmt_ms([r['conclusion'] for r in rs])} | {fmt_ms([r['pickup'] for r in rs])} | "
            f"{fmt_ms([r['engagement'] for r in rs])} | {sum(len(r['harmful']) for r in rs)} / "
            f"{sum(r['changes'] for r in rs)} | {sum(1 for r in rs if r['harmful'])}/{len(rs)} | "
            f"{sum(r['expired'] + r['lapsed'] for r in rs)} | "
            f"{'—' if not mttr else f'median {st.median(mttr):.0f}, max {max(mttr)}'} | "
            f"{'—' if not tails else f'{sum(1 for t in tails if t > 0.05)}/{len(tails)} arms'} |")
    out += ["", "## Harmful changes", ""]
    kinds = Counter()
    for r in rows:
        for h in r["harmful"]:
            kind = "prompt" if "prompt_version" in h["dims"] else "caller_id" if h["did"] < -0.02 else \
                "launch (W/V + setup)" if "cohorts" in h["dims"] else "W/V"
            kinds[kind] += 1
            out.append(f"- {r['scenario']} seed {r['seed']}: {h['wf']} v{h['v']} {h['actor']} {h['dims']} "
                       f"engageΔ={h['engage']:+.3f} didΔ={h['did']:+.3f} → {kind}")
    out += ["", "By kind: " + (", ".join(f"{k} {v}" for k, v in kinds.most_common()) or "none"), ""]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenarios", nargs="*", default=DEFAULT)
    ap.add_argument("--label", required=True)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 4) // 2))
    ap.add_argument("--port", type=int, default=8800)
    ap.add_argument("--set", default="", help="JSON of controller settings to override for this sweep")
    a = ap.parse_args()
    jobs = [(sc, 1000 + i) for sc in a.scenarios for i in range(a.seeds)]
    with ThreadPoolExecutor(a.jobs) as ex:
        futs = [ex.submit(run_one, sc, seed, a.port + n, a.label, a.set) for n, (sc, seed) in enumerate(jobs)]
        rows = []
        for f, (sc, seed) in zip(futs, jobs):
            try:
                rows.append(f.result())
            except Exception as e:   # one broken run shouldn't hide the rest; it is reported
                print(f"FAILED {sc} seed {seed}: {e}", file=sys.stderr)
    (ROOT / "runs/sweep").mkdir(parents=True, exist_ok=True)
    (ROOT / f"runs/sweep/{a.label}.json").write_text(json.dumps(rows, indent=1))
    md = report(a.label + (f" (settings {a.set})" if a.set else ""), rows)
    (ROOT / f"reports/sweep_{a.label}.md").write_text(md)
    print(md)


if __name__ == "__main__":
    main()
