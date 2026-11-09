# Controller runbook

For the engineer who owns this when its author is away. Design rationale lives in `SUBMISSION.md`; this is how to
run, debug and extend it.

## Run

```bash
./run.sh http://127.0.0.1:8700                         # creates .venv on first run; state in state/controller.db
CONTROLLER_DB=state/x.db ./run.sh http://...           # another store
scripts/run_scenario.sh scenarios/public_02_incidents.yaml 8702   # sim + controller + grade, end to end
scripts/crash_test.sh scenarios/public_02_incidents.yaml 6 8790   # kill/restart test (crash points + SIGKILLs), verified
scripts/ablation.sh scenarios/public_01_dev.yaml did 8721         # one module off: what is that lever worth?
python tests/scenarios/make_variants.py                         # rebuild the hidden-like test scenarios
.venv/bin/python -m pytest -q tests                    # unit + contract tests (in-process simulator)
```

`CONTROLLER_MODULES=incidents,did` (comma list; default all four) runs a subset of modules. Use it for ablations, or to
switch a misbehaving lever off without a deploy: the switched-off module proposes nothing and leaves its dimension as is.

Restarting is always safe: `./run.sh` against the same simulator resumes from the store. A store that belongs to a
different simulator world (other scenario, or time went backwards) is renamed `*.old-<ts>` and a fresh one starts.

## Where things are

| file | what |
|---|---|
| `controller/loop.py` | advance → ingest → reconcile → modules → governance; tick sizing |
| `controller/ingest.py` | chunk → aggregates, one transaction per chunk (`chunks` table is the watermark) |
| `controller/governance.py` | the only code that changes config; proposal lifecycle and its state machine |
| `controller/intents.py` | the intent type, config diffs, allocation normalisation (1/4096 quantum — see docstring) |
| `controller/modules/*.py` | policies: `did`, `incidents`, `experiments`, `schedule`. Each emits intents, never calls the API to change config |
| `controller/settings.py` | every threshold and voluntary tenant preference, each with a one-line reason |
| `controller/report.py` | `why`, `lead`, `view`, `health` |
| `controller/faults.py` | crash injection used by the crash test |

## Debugging a decision

1. `python -m controller why --wf <wf> --at "D3 14:00" --db <db>` — the change, who approved it, the request the
   approver saw, the module's decision trail, and KPIs 24h either side.
2. `sqlite3 <db> "select minute, kind, summary from decisions where wf='<wf>' order by id"` — everything the
   controller decided or observed for a workflow, in order. `detail` holds the numbers behind each line.
3. Module state: `select value from state where module='experiments' and key='<wf>'` (also `did`, `incidents`,
   `schedule`, `supervisor`, `validations`).
4. Proposals: `select proposal_id, path, status, approval_id, reasons, outcome from proposals where wf='<wf>'`.

Statistical decisions are deterministic (posterior draws are seeded from the counts), so re-running
`stats.compare_arms` on the counts in a decision's `detail` reproduces it exactly.

## Alerts

| severity | meaning | first look |
|---|---|---|
| page | module crashed for a workflow (it is left unchanged) | `runs/controller_*.log` traceback; `decisions` row |
| page | apply failed with an unexpected error | `proposals.outcome` for that `ref` |
| page | incident with no validated fix / fix didn't reduce flags | `state` incidents for the wf; consider a manual prompt revert via the client |
| page | out of credits (402) | `health` credit line; who spent it in `decisions` (`validation_run`, `llm_suggest`) |
| ticket | auto-apply or approval request refused | `proposals.outcome` has the simulator's reasons — usually a policy changed under us |
| ticket | safe incident fix lowered engagement | product decision: which prompt to keep |

Rejections, expiries, stale bases and lapses are normal governance and don't alert; they show in `view`.

## Extending

A new lever is a new module: subclass `modules.base.Module`, implement `intents(ctx, **kw)` returning `Intent`s with
an honest `dry_run`, `impact` (use `base.impact_score`) and `affected_leads`, persist state with `self.load/save`,
record anything noteworthy with `self.s.decide(...)`, and register it in `modules/__init__.py`. Set `auto="never"` if
customers would hear the change; `urgent=True` only for risk-reducing moves. Governance handles batching, quota,
timing, freezes, crash safety and the audit trail.

## Known sharp edges

- The simulator compares allocations exactly; always build distributions with `intents.normalise_dist`.
- Hour windows: use `ctx.hour_keys(n)` (n complete dialling hours + the current partial hour).
- Any auto-apply makes an in-flight approval stale; governance freezes non-urgent auto-applies for that reason.
- `next_campaign_only` workflows keep a campaign's allocation for its whole cadence: changes take a day to show
  and mistakes last ~3 days.
