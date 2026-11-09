# Audit examples (public_02, from the controller store)

Regenerate: see the commands below; they read only `state/public_02_incidents.db`.

```
$ python -m controller why --wf ks_cancel --at 'D3 13:00'
# Why did ks_cancel change around D3 13:00?

## v8 at D3 11:30 — supervisor, changed prompt_version

Edited directly by the client's supervisor (bypasses governance). Controller response:
- D3 11:30 supervisor_edit: supervisor changed prompt_version (v8); respecting it: no proposals on these dims for a while
- D3 11:45 incident_opened: supervisor prompt change to P2 at D3 11:30 fails validation: pass rate 0.935 on n=200 vs the client's minimum 0.97

**What happened next** (24h before → 24h after): pickup 0.26 → 0.259, engagement 0.504 → 0.516, hallucination flags 0.0104 → 0.0177
- D3 13:00 applied: apr_00008 applied as v9
- D3 14:30 incident_resolved: inc-ks_cancel-5025 resolved: flags on P1 at 0.0% (normal 1.4%); time to fix 1.2h; engagement holding
- D3 16:30 experiment_winner: exp-ks_cancel-welcome_message-1: W2 beats W1 on engagement (P(best)=0.952, lift +10.9% [+3.3%, +18.9%], n=1027); promote with 20% holdout on W1
- D4 08:00 experiment_drop: exp-ks_cancel-voice-2: dropping V2 (P(beats V1) <= 0.025)
- D4 13:15 applied: apr_00010 applied as v10

## v9 at D3 13:00 — controller_approved, changed prompt_version

**Proposal** `ks_cancel-urgent-5025-v8-ea65b72e` requested D3 11:45, approval `apr_00008` approved by the client approver at 12:37, applied D3 13:00.
- Summary: Revert prompt P2 -> P1: P2 fails validation: pass rate 0.935 on n=200 (val_00001) vs your minimum 0.97 (reverses a supervisor change made at D3 11:30)
- Impact score 0.9, affected leads 3623
- Diff: `{"prompt_version": {"from": "P2", "to": "P1"}}`
- Rationale: Incident inc-ks_cancel-5025: P2 fails validation: pass rate 0.935 on n=200 (val_00001) vs your minimum 0.97; it reached production without validation. P1 ran 20363 connected calls here at a 1.4% flag rate and passed validation at 0.990 (n=200, policy minimum 0.97). After apply we verify flags return to normal and engagement does not drop.
- Evidence: {"validation_run_id": "val_00002"}
- Dry run (prompt_version): `{"method": "production flag rates per prompt in this workflow + validation run", "current": {"prompt": "P2", "evidence": {"source": "validation of a supervisor prompt change", "validation_run_id": "val_00001", "n": 200, "pass_rate": 0.935, "min_pass": 0.97, "rate": 0.065, "connected": 200, "flags": 13, "expected": null, "p_value": null}, "conn": 26, "flags": 3, "eng": 11}, "candidate": {"prompt": "P1", "flag_rate": 0.013732101842349607, "conn": 20363, "flags": 280, "eng": 10285}, "validation": {`

**Decision trail for inc-ks_cancel-5025:**
- D3 11:45 incident_opened: supervisor prompt change to P2 at D3 11:30 fails validation: pass rate 0.935 on n=200 vs the client's minimum 0.97
- D3 13:00 incident_fix_live: prompt is now P1; verifying
- D3 14:30 incident_resolved: inc-ks_cancel-5025 resolved: flags on P1 at 0.0% (normal 1.4%); time to fix 1.2h; engagement holding

**What happened next** (24h before → 24h after): pickup 0.258 → 0.262, engagement 0.511 → 0.506, hallucination flags 0.017 → 0.0119
- D3 14:30 incident_resolved: inc-ks_cancel-5025 resolved: flags on P1 at 0.0% (normal 1.4%); time to fix 1.2h; engagement holding
- D3 16:30 experiment_winner: exp-ks_cancel-welcome_message-1: W2 beats W1 on engagement (P(best)=0.952, lift +10.9% [+3.3%, +18.9%], n=1027); promote with 20% holdout on W1
- D4 08:00 experiment_drop: exp-ks_cancel-voice-2: dropping V2 (P(beats V1) <= 0.025)
- D4 13:15 applied: apr_00010 applied as v10
- D5 12:45 applied: apr_00013 applied as v11

```

```
$ python -m controller why --wf nw_renewal --at 'D5 12:00'
# Why did nw_renewal change around D5 12:00?

## v11 at D5 12:00 — controller_approved, changed welcome_message

**Proposal** `nw_renewal-urgent-7800-v10-12c1198e` requested D5 10:00, approval `apr_00012` approved by the client approver at 11:45, applied D5 12:00.
- Summary: Set welcome_message back to W1 (promoted option faded)
- Impact score 0.988, affected leads 2574
- Diff: `{"allocations.default.welcome_message": {"from": {"W1": 0.199951171875, "W3": 0.800048828125}, "to": {"W1": 1.0}}}`
- Rationale: exp-nw_renewal-welcome_message-1: the promoted option is now worse than the holdout; reverting.
- Evidence: {}
- Dry run (allocations.default.welcome_message): `{"method": "posterior mean engagement per arm from calls that actually ran with it, replayed over the last 3 days of connected-call volume", "engagement_old": 0.5158, "engagement_new": 0.6055, "connected_per_day": 1079, "extra_conclusions_per_day": 96.7, "arms": {"W1": {"lift": 0.0, "lift_ci": [0.0, 0.0], "mean": 0.6055, "n": 216, "p_beats_incumbent": 0.0, "p_best": 0.9983, "rate": 0.6065, "succ": 131}, "W3": {"lift": -0.1852, "lift_ci": [-0.2799, -0.069], "mean": 0.4934, "n": 825, "p_beats_incu`

**Decision trail for exp-nw_renewal-welcome_message-1:**
- D0 00:00 experiment_planned: exp-nw_renewal-welcome_message-1: test W2, W3 against W1 on welcome_message
- D0 11:15 experiment_live: exp-nw_renewal-welcome_message-1 explore allocation live: {'W1': 0.5, 'W2': 0.25, 'W3': 0.25}
- D1 14:30 experiment_winner: exp-nw_renewal-welcome_message-1: W3 beats W1 on engagement (P(best)=0.980, lift +16.9% [+5.6%, +28.9%], n=317); promote with 20% holdout on W1
- D1 16:00 experiment_live: exp-nw_renewal-welcome_message-1 exploit allocation live: {'W1': 0.199951171875, 'W3': 0.800048828125}
- D4 15:00 experiment_decay_suspected: exp-nw_renewal-welcome_message-1: W3 -7.8% vs holdout W1 over the last 36h (P(worse)=0.93); confirming at the next check
- D5 09:00 experiment_decay: exp-nw_renewal-welcome_message-1: W3 has stopped winning: over the last 36h it is -18.5% vs holdout W1 (P(worse)=1.00); rolling back to W1
- D5 12:00 experiment_settled: exp-nw_renewal-welcome_message-1: welcome_message settled on {'W1': 1.0}

**What happened next** (24h before → 24h after): pickup 0.289 → 0.286, engagement 0.507 → 0.572, hallucination flags 0.0192 → 0.0155
- D5 15:00 auto_applied: v12: rebalance load across healthy caller IDs by measured pickup (D1 1.00, D2 1.02, D3 1.00, D4 0.95)

```

```
$ python -m controller lead --lead ks_cancel:l00022534
# What ks_cancel:l00022534 heard (ks_cancel)

- D1 18:37 attempt 1: welcome W1, voice V1, caller ID D1, prompt P1, cohort age_60plus_t1, config v5 → not connected
- D3 11:51 attempt 2: welcome W1, voice V1, caller ID D1, prompt P2, cohort age_60plus_t1, config v8 → connected, dropped
- D3 17:51 attempt 3: welcome W1, voice V1, caller ID D3, prompt P1, cohort age_60plus_t1, config v9 → not connected

## Why those variants were live
For each config version the customer was dialled under, the change that last set each dimension:
### config v5
- welcome_message: set in v3 at D0 12:15 by controller_approved (approval apr_00003) — Test welcome_message options W1 50%, W2 25%, W3 25%; Test voice options V1 50%, V2 17%, V3 17%, V4 17%; Define 12 cohorts (age band x city tier) used for call timing and reporting; Call each cohort in its better hours (predicted pickup +2.7%)
- voice: set in v3 at D0 12:15 by controller_approved (approval apr_00003) — Test welcome_message options W1 50%, W2 25%, W3 25%; Test voice options V1 50%, V2 17%, V3 17%, V4 17%; Define 12 cohorts (age band x city tier) used for call timing and reporting; Call each cohort in its better hours (predicted pickup +2.7%)
- caller_id: set in v5 at D1 09:00 by controller_auto — rebalance load across healthy caller IDs by measured pickup (D1 0.98, D2 1.00, D3 1.09). Caller IDs are randomised per dial, so each number's pickup is compared with the other numbers in the same hour
- prompt_version: business default configuration (never changed before v5)
### config v8
- welcome_message: set in v3 at D0 12:15 by controller_approved (approval apr_00003) — Test welcome_message options W1 50%, W2 25%, W3 25%; Test voice options V1 50%, V2 17%, V3 17%, V4 17%; Define 12 cohorts (age band x city tier) used for call timing and reporting; Call each cohort in its better hours (predicted pickup +2.7%)
- voice: set in v3 at D0 12:15 by controller_approved (approval apr_00003) — Test welcome_message options W1 50%, W2 25%, W3 25%; Test voice options V1 50%, V2 17%, V3 17%, V4 17%; Define 12 cohorts (age band x city tier) used for call timing and reporting; Call each cohort in its better hours (predicted pickup +2.7%)
- caller_id: set in v7 at D2 11:30 by controller_auto — stop dialling from degraded caller ID(s) D2. Caller IDs are randomised per dial, so each number's pickup is compared with the other numbers in the same hours. Relative pickup over the last 24 dialling
- prompt_version: set in v8 at D3 11:30 by supervisor
### config v9
- welcome_message: set in v3 at D0 12:15 by controller_approved (approval apr_00003) — Test welcome_message options W1 50%, W2 25%, W3 25%; Test voice options V1 50%, V2 17%, V3 17%, V4 17%; Define 12 cohorts (age band x city tier) used for call timing and reporting; Call each cohort in its better hours (predicted pickup +2.7%)
- voice: set in v3 at D0 12:15 by controller_approved (approval apr_00003) — Test welcome_message options W1 50%, W2 25%, W3 25%; Test voice options V1 50%, V2 17%, V3 17%, V4 17%; Define 12 cohorts (age band x city tier) used for call timing and reporting; Call each cohort in its better hours (predicted pickup +2.7%)
- caller_id: set in v7 at D2 11:30 by controller_auto — stop dialling from degraded caller ID(s) D2. Caller IDs are randomised per dial, so each number's pickup is compared with the other numbers in the same hours. Relative pickup over the last 24 dialling
- prompt_version: set in v9 at D3 13:00 by controller_approved (approval apr_00008) — Revert prompt P2 -> P1: P2 fails validation: pass rate 0.935 on n=200 (val_00001) vs your minimum 0.97 (reverses a supervisor change made at D3 11:30)
```

```
$ python -m controller view --wf ks_cancel
# Supervisor view — D10 00:00

## ks_cancel
Today: pickup None (yesterday 0.239), engagement None (yesterday 0.517), 0 dials

**Testing / winning**
- voice: closed, allocation {'V3': 1.0}, leading: V3 (P(best)=0.71, lift +4.0%)
- welcome_message: exploit, allocation {'W1': 0.199951171875, 'W2': 0.800048828125}, leading: W2 (P(best)=0.78, lift +4.6%)
- caller IDs: D1=healthy, D2=degraded, D3=healthy
**Waiting on you:** nothing
**Changed in the last 24h**
- nothing

```

```
$ python -m controller health
# Controller health — last tick D10 00:00
- ingested through: D9 21:00 (lag vs last tick: 180 sim minutes)
- chunks: 491, events: 324345, ingest 62,771 events/s
- controller era: 324,345 events, ingest 5.2s + decide 30.9s over 10.0 sim days (49s wall, 5s wall per sim day)
- peak decide time per tick: 0.18s, peak RSS 223 MB
- credits: 200 → 196
- decisions: approval_requested=14, approval_approved=13, applied=13, auto_applied=12, experiment_live=8, experiment_planned=6, did_probe_healthy=5, experiment_settled=5, experiment_drop=4, experiment_closed=4, schedule_fit=3, experiment_winner=2, supervisor_edit=2, validation_run=2, did_degraded=1, incident_opened=1, incident_fix_live=1, incident_resolved=1, experiment_decay_suspected=1, experiment_decay=1, approval_rejected=1

## Recent alerts
- none
```
