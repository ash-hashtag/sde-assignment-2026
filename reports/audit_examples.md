# Audit examples (public_02, from the controller store)

Regenerate: see the commands below; they read only `state/public_02_incidents.db`.

```
$ python -m controller why --wf ks_cancel --at 'D3 13:00'
# Why did ks_cancel change around D3 13:00?

## v8 at D3 11:30 — supervisor, changed prompt_version

Edited directly by the client's supervisor (bypasses governance). Controller response:
- D3 11:30 supervisor_edit: supervisor changed prompt_version (v8); respecting it: no proposals on these dims for a while
- D3 11:45 incident_opened: supervisor prompt change to P2 at D3 11:30 fails validation: pass rate 0.935 on n=200 vs the client's minimum 0.97

**What happened next** (24h before → 24h after): pickup 0.26 → 0.263, engagement 0.498 → 0.504, hallucination flags 0.0152 → 0.0206
- D3 12:45 experiment_winner: exp-ks_cancel-welcome_message-1: W2 beats W1 on engagement (P(best)=0.955, lift +11.6% [+3.7%, +19.8%], n=966); promote with 20% holdout on W1
- D3 13:00 applied: apr_00009 applied as v9
- D3 14:30 incident_resolved: inc-ks_cancel-5025 resolved: flags on P1 at 1.3% (normal 1.4%); time to fix 1.2h; engagement holding
- D4 13:45 applied: apr_00010 applied as v10

## v9 at D3 13:00 — controller_approved, changed prompt_version

**Proposal** `ks_cancel-urgent-5025-v8-ea65b72e` requested D3 11:45, approval `apr_00009` approved by the client approver at 12:37, applied D3 13:00.
- Summary: Revert prompt P2 -> P1: P2 fails validation: pass rate 0.935 on n=200 (val_00001) vs your minimum 0.97 (reverses a supervisor change made at D3 11:30)
- Impact score 0.9, affected leads 3637
- Diff: `{"prompt_version": {"from": "P2", "to": "P1"}}`
- Rationale: Incident inc-ks_cancel-5025: P2 fails validation: pass rate 0.935 on n=200 (val_00001) vs your minimum 0.97; it reached production without validation. P1 ran 20402 connected calls here at a 1.4% flag rate and passed validation at 0.990 (n=200, policy minimum 0.97). After apply we verify flags return to normal and engagement does not drop.
- Evidence: {"validation_run_id": "val_00002"}
- Dry run (prompt_version): `{"method": "production flag rates per prompt in this workflow + validation run", "current": {"prompt": "P2", "evidence": {"source": "validation of a supervisor prompt change", "validation_run_id": "val_00001", "n": 200, "pass_rate": 0.935, "min_pass": 0.97, "rate": 0.065, "connected": 200, "flags": 13, "expected": null, "p_value": null}, "conn": 33, "flags": 0, "eng": 20}, "candidate": {"prompt": "P1", "flag_rate": 0.013852307091991025, "conn": 20402, "flags": 283, "eng": 10311}, "validation": {`

**Decision trail for inc-ks_cancel-5025:**
- D3 11:45 incident_opened: supervisor prompt change to P2 at D3 11:30 fails validation: pass rate 0.935 on n=200 vs the client's minimum 0.97
- D3 13:00 incident_fix_live: prompt is now P1; verifying
- D3 14:30 incident_resolved: inc-ks_cancel-5025 resolved: flags on P1 at 1.3% (normal 1.4%); time to fix 1.2h; engagement holding

**What happened next** (24h before → 24h after): pickup 0.262 → 0.263, engagement 0.504 → 0.511, hallucination flags 0.0175 → 0.0166
- D3 14:30 incident_resolved: inc-ks_cancel-5025 resolved: flags on P1 at 1.3% (normal 1.4%); time to fix 1.2h; engagement holding
- D4 13:45 applied: apr_00010 applied as v10


$ python -m controller why --wf nw_renewal --at 'D5 11:45'
# Why did nw_renewal change around D5 11:45?

## v9 at D5 09:00 — controller_auto, changed caller_id

**Auto-applied** `nw_renewal-auto-7740-v8-24b92750` under the workflow's auto-apply policy (no human approval needed for caller_id).
- Rationale: rebalance load across healthy caller IDs by measured pickup (D1 1.02, D2 0.99, D3 0.99, D4 1.00). Caller IDs are randomised per dial, so each number's pickup is compared with the other numbers in the same hours. Relative pickup over the last 24 dialling hours: D1=1.00, D2=0.94, D3=0.96, D4=1.07.
- Dry run (allocations.default.caller_id): `{"method": "hour-matched pickup ratio per caller ID over the last 24 dialling hours, weighted by the new allocation", "relative_health": {"D1": 1.001, "D2": 0.942, "D3": 0.958, "D4": 1.068}, "expected_pickup_change": -0.0105, "expected_extra_conclusions_per_day": -6.1, "status": {"D1": "healthy", "D2": "healthy", "D3": "healthy", "D4": "healthy"}}`

**What happened next** (24h before → 24h after): pickup 0.306 → 0.295, engagement 0.495 → 0.542, hallucination flags 0.0127 → 0.0132
- D5 11:45 applied: apr_00011 applied as v10

## v10 at D5 11:45 — controller_approved, changed welcome_message

**Proposal** `nw_renewal-urgent-7800-v9-6ae03921` requested D5 10:00, approval `apr_00011` approved by the client approver at 11:20, applied D5 11:45.
- Summary: Set welcome_message back to W1 (promoted option faded)
- Impact score 0.996, affected leads 2601
- Diff: `{"allocations.default.welcome_message": {"from": {"W1": 0.199951171875, "W3": 0.800048828125}, "to": {"W1": 1.0}}}`
- Rationale: exp-nw_renewal-welcome_message-1: the promoted option is now worse than the holdout; reverting.
- Evidence: {}
- Dry run (allocations.default.welcome_message): `{"method": "posterior mean engagement per arm from calls that actually ran with it, replayed over the last 3 days of connected-call volume", "engagement_old": 0.4977, "engagement_new": 0.6127, "connected_per_day": 1070, "extra_conclusions_per_day": 123.1, "arms": {"W1": {"lift": 0.0, "lift_ci": [0.0, 0.0], "mean": 0.6127, "n": 202, "p_beats_incumbent": 0.0, "p_best": 0.9997, "rate": 0.6139, "succ": 124}, "W3": {"lift": -0.2347, "lift_ci": [-0.3247, -0.1247], "mean": 0.4689, "n": 900, "p_beats_in`

**Decision trail for exp-nw_renewal-welcome_message-1:**
- D0 00:00 experiment_planned: exp-nw_renewal-welcome_message-1: test W2, W3 against W1 on welcome_message
- D0 11:15 experiment_live: exp-nw_renewal-welcome_message-1 explore allocation live: {'W1': 0.5, 'W2': 0.25, 'W3': 0.25}
- D1 14:15 experiment_winner: exp-nw_renewal-welcome_message-1: W3 beats W1 on engagement (P(best)=0.965, lift +15.5% [+3.8%, +28.2%], n=319); promote with 20% holdout on W1
- D2 10:15 experiment_live: exp-nw_renewal-welcome_message-1 exploit allocation live: {'W1': 0.199951171875, 'W3': 0.800048828125}
- D4 15:00 experiment_decay_suspected: exp-nw_renewal-welcome_message-1: W3 -8.2% vs holdout W1 over the last 36h (P(worse)=0.93); confirming at the next check
- D5 09:00 experiment_decay: exp-nw_renewal-welcome_message-1: W3 has stopped winning: over the last 36h it is -23.5% vs holdout W1 (P(worse)=1.00); rolling back to W1
- D5 11:45 experiment_settled: exp-nw_renewal-welcome_message-1: welcome_message settled on {'W1': 1.0}

**What happened next** (24h before → 24h after): pickup 0.304 → 0.296, engagement 0.499 → 0.557, hallucination flags 0.0119 → 0.0141


$ python -m controller lead --lead ks_cancel:l00026406
# What ks_cancel:l00026406 heard (ks_cancel)

- D3 11:38 attempt 1: welcome W2, voice V4, caller ID D1, prompt P2, cohort age_18_30_t2, config v8 → engaged

## Why those variants were live
For each config version the customer was dialled under, the change that last set each dimension:
### config v8
- welcome_message: set in v3 at D0 12:15 by controller_approved (approval apr_00003) — Test welcome_message options W1 50%, W2 25%, W3 25%; Test voice options V1 50%, V2 17%, V3 17%, V4 17%; Define 12 cohorts (age band x city tier) used for call timing and reporting; Call each cohort in its better hours (predicted pickup +2.7%)
- voice: set in v3 at D0 12:15 by controller_approved (approval apr_00003) — Test welcome_message options W1 50%, W2 25%, W3 25%; Test voice options V1 50%, V2 17%, V3 17%, V4 17%; Define 12 cohorts (age band x city tier) used for call timing and reporting; Call each cohort in its better hours (predicted pickup +2.7%)
- caller_id: set in v7 at D2 11:15 by controller_auto — stop dialling from degraded caller ID(s) D2. Caller IDs are randomised per dial, so each number's pickup is compared with the other numbers in the same hours. Relative pickup over the last 24 dialling
- prompt_version: set in v8 at D3 11:30 by supervisor

$ python -m controller view --wf ks_cancel
# Supervisor view — D10 00:00

## ks_cancel
Today: pickup None (yesterday 0.243), engagement None (yesterday 0.484), 0 dials

**Testing / winning**
- voice: closing, allocation {'V1': 0.114990234375, 'V2': 0.58544921875, 'V4': 0.299560546875}, leading: V2 (P(best)=0.56, lift +2.8%)
- welcome_message: closed, allocation {'W1': 1.0}, leading: W1 (P(best)=0.97, lift +0.0%)
- caller IDs: D1=healthy, D2=degraded, D3=healthy
**Waiting on you:** nothing
**Changed in the last 24h**
- D9 09:00 auto_applied: v11: Set welcome_message back to W1 (promoted option faded) (stepped)
- D9 09:15 auto_applied: v12: Set welcome_message back to W1 (promoted option faded) (stepped)
- D9 09:30 auto_applied: v13: Set welcome_message back to W1 (promoted option faded) (stepped)
- D9 09:45 auto_applied: v14: Set welcome_message back to W1 (promoted option faded) (stepped)
- D9 10:00 auto_applied: v15: Set welcome_message back to W1 (promoted option faded)


$ python -m controller health
# Controller health — last tick D10 00:00
- ingested through: D9 21:00 (lag vs last tick: 180 sim minutes)
- chunks: 491, events: 324341, ingest 66,690 events/s
- controller era: 324,341 events, ingest 4.9s + decide 32.2s over 10.0 sim days (53s wall, 5s wall per sim day)
- peak decide time per tick: 0.17s, peak RSS 216 MB
- credits: 200 → 196
- decisions: auto_applied=15, approval_requested=11, approval_approved=9, applied=9, experiment_live=8, experiment_planned=6, did_probe_healthy=5, experiment_closed=5, schedule_fit=3, did_degraded=2, experiment_winner=2, approval_rejected=2, supervisor_edit=2, validation_run=2, experiment_decay_suspected=2, experiment_decay=2, experiment_settled=2, experiment_drop=1, incident_opened=1, incident_fix_live=1, incident_resolved=1

## Recent alerts
- none
```
