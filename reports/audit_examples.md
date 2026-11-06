# Audit examples (public_02, from the controller store)

```
$ python -m controller why --wf ks_cancel --at 'D3 17:00' --db state/public_02_incidents.db
# Why did ks_cancel change around D3 17:00?

## v9 at D3 11:30 — supervisor, changed prompt_version

Edited directly by the client's supervisor (bypasses governance). Controller response:
- D3 11:30 supervisor_edit: supervisor changed prompt_version (v9); respecting it: no proposals on these dims for a while
- D3 13:15 incident_opened: hallucination spike on prompt P2: 11 flags in 202 connected calls over 3h (5.4% vs normal 1.4%, p=1.4e-04); prompt was set by a supervisor at D3 11:30

**What happened next** (24h before → 24h after): pickup 0.268 → 0.254, engagement 0.516 → 0.497, hallucination flags 0.0078 → 0.027
- D3 14:30 applied: apr_00010 applied as v10
- D3 16:00 incident_resolved: inc-ks_cancel-5115 resolved: flags on P1 at 2.0% (normal 1.4%); time to fix 1.2h; engagement holding
- D4 08:00 experiment_drop: exp-ks_cancel-voice-2: dropping V4 (P(beats V1) <= 0.025)
- D4 10:15 auto_applied: v11: rebalance load across healthy caller IDs by measured pickup (D1 0.98, D3 1.03)
- D4 14:45 applied: apr_00012 applied as v12

## v10 at D3 14:30 — controller_approved, changed prompt_version

**Proposal** `ks_cancel-urgent-5115-v9-0abd51ec` requested D3 13:15, approval `apr_00010` approved by the client approver at 14:04, applied D3 14:30.
- Summary: Revert prompt P2 -> P1: hallucination flags at 5.5% vs normal 1.4% (reverses a supervisor change made at D3 11:30)
- Impact score 0.9, affected leads 3545
- Diff: `{"prompt_version": {"from": "P2", "to": "P1"}}`
- Rationale: Incident inc-ks_cancel-5115: 11 hallucination flags in 202 connected calls on P2 (p=1.4e-04 against the normal rate). P1 ran 20399 connected calls here at a 1.3% flag rate and passed validation at 0.985 (n=200, policy minimum 0.97). After apply we verify flags return to normal and engagement does not drop.
- Evidence: {"validation_run_id": "val_00001"}
- Dry run (prompt_version): `{"method": "production flag rates per prompt in this workflow + validation run", "current": {"prompt": "P2", "flag_rate": 0.0545, "conn": 202, "flags": 11, "eng": 88}, "candidate": {"prompt": "P1", "flag_rate": 0.013464071418117956, "conn": 20399, "flags": 275, "eng": 10316}, "validation": {"validation_run_id": "val_00001", "n": 200, "pass_rate": 0.985}}`

**Decision trail for inc-ks_cancel-5115:**
- D3 13:15 incident_opened: hallucination spike on prompt P2: 11 flags in 202 connected calls over 3h (5.4% vs normal 1.4%, p=1.4e-04); prompt was set by a supervisor at D3 11:30
- D3 14:30 incident_fix_live: prompt is now P1; verifying
- D3 16:00 incident_resolved: inc-ks_cancel-5115 resolved: flags on P1 at 2.0% (normal 1.4%); time to fix 1.2h; engagement holding

**What happened next** (24h before → 24h after): pickup 0.266 → 0.258, engagement 0.507 → 0.515, hallucination flags 0.0172 → 0.0186
- D3 16:00 incident_resolved: inc-ks_cancel-5115 resolved: flags on P1 at 2.0% (normal 1.4%); time to fix 1.2h; engagement holding
- D4 08:00 experiment_drop: exp-ks_cancel-voice-2: dropping V4 (P(beats V1) <= 0.025)
- D4 10:15 auto_applied: v11: rebalance load across healthy caller IDs by measured pickup (D1 0.98, D3 1.03)
- D4 14:45 applied: apr_00012 applied as v12


$ python -m controller why --wf nw_renewal --at 'D6 10:15' --db state/public_02_incidents.db
# Why did nw_renewal change around D6 10:15?

## v11 at D6 10:15 — controller_approved, changed welcome_message

**Proposal** `nw_renewal-urgent-8295-v10-197fe3be` requested D5 18:15, approval `apr_00014` approved by the client approver at 10:00, applied D6 10:15.
- Summary: Set welcome_message back to W1 (promoted option faded)
- Impact score 0.99, affected leads 2241
- Diff: `{"allocations.default.welcome_message": {"from": {"W1": 0.14990234375, "W3": 0.85009765625}, "to": {"W1": 1.0}}}`
- Rationale: exp-nw_renewal-welcome_message-1: the promoted option is now worse than the holdout; reverting.
- Evidence: {}
- Dry run (allocations.default.welcome_message): `{"method": "posterior mean engagement per arm from calls that actually ran with it, replayed over the last 3 days of connected-call volume", "engagement_old": 0.4945, "engagement_new": 0.5909, "connected_per_day": 1056, "extra_conclusions_per_day": 101.8, "arms": {"W1": {"lift": 0.0, "lift_ci": [0.0, 0.0], "mean": 0.5909, "n": 257, "p_beats_incumbent": 0.0, "p_best": 0.9996, "rate": 0.5914, "succ": 152}, "W3": {"lift": -0.1921, "lift_ci": [-0.2771, -0.0895], "mean": 0.4775, "n": 1378, "p_beats_i`

**Decision trail for exp-nw_renewal-welcome_message-1:**
- D0 00:00 experiment_planned: exp-nw_renewal-welcome_message-1: test W2, W3 against W1 on welcome_message
- D0 11:15 experiment_live: exp-nw_renewal-welcome_message-1 explore allocation live: {'W1': 0.5, 'W2': 0.25, 'W3': 0.25}
- D1 14:15 experiment_winner: exp-nw_renewal-welcome_message-1: W3 beats W1 on engagement (P(best)=0.965, lift +15.5% [+3.8%, +28.2%], n=319); promote with 15% holdout on W1
- D1 18:15 experiment_live: exp-nw_renewal-welcome_message-1 exploit allocation live: {'W1': 0.14990234375, 'W3': 0.85009765625}
- D5 09:00 experiment_decay_suspected: exp-nw_renewal-welcome_message-1: W3 -18.5% vs holdout W1 over the last 36h (P(worse)=0.99); confirming at the next check
- D5 15:00 experiment_decay: exp-nw_renewal-welcome_message-1: W3 has stopped winning: over the last 36h it is -19.2% vs holdout W1 (P(worse)=1.00); rolling back to W1
- D6 10:15 experiment_settled: exp-nw_renewal-welcome_message-1: welcome_message settled on {'W1': 1.0}

**What happened next** (24h before → 24h after): pickup 0.29 → 0.301, engagement 0.496 → 0.56, hallucination flags 0.0201 → 0.0166


$ python -m controller lead --lead ks_cancel:l00024204 --db state/public_02_incidents.db
# What ks_cancel:l00024204 heard (ks_cancel)

- D3 09:27 attempt 1: welcome W2, voice V1, caller ID D3, prompt P1, cohort age_31_45_t2, config v8 → not connected
- D3 11:52 attempt 2: welcome W2, voice V3, caller ID D1, prompt P2, cohort age_31_45_t2, config v9 → connected, dropped
- D4 16:43 attempt 3: welcome W2, voice V1, caller ID D1, prompt P1, cohort age_31_45_t2, config v12 → not connected

## Why those variants were live
For each config version the customer was dialled under, the change that last set each dimension:
### config v8
- welcome_message: set in v7 at D2 17:00 by controller_approved (approval apr_00008) — Promote welcome_message W2 to 85% (keep W1 at 15% as holdout)
- voice: set in v3 at D0 12:15 by controller_approved (approval apr_00003) — Test welcome_message options W1 50%, W2 25%, W3 25%; Test voice options V1 50%, V2 17%, V3 17%, V4 17%; Define 12 cohorts (age band x city tier) used for call timing and reporting; Call each cohort in its better hours (predicted pickup +2.7%)
- caller_id: set in v8 at D3 09:00 by controller_auto — rebalance load across healthy caller IDs by measured pickup (D1 0.90, D3 1.19). Caller IDs are randomised per dial, so each number's pickup is compared with the other numbers in the same hours. Relati
- prompt_version: business default configuration (never changed before v8)
### config v9
- welcome_message: set in v7 at D2 17:00 by controller_approved (approval apr_00008) — Promote welcome_message W2 to 85% (keep W1 at 15% as holdout)
- voice: set in v3 at D0 12:15 by controller_approved (approval apr_00003) — Test welcome_message options W1 50%, W2 25%, W3 25%; Test voice options V1 50%, V2 17%, V3 17%, V4 17%; Define 12 cohorts (age band x city tier) used for call timing and reporting; Call each cohort in its better hours (predicted pickup +2.7%)
- caller_id: set in v8 at D3 09:00 by controller_auto — rebalance load across healthy caller IDs by measured pickup (D1 0.90, D3 1.19). Caller IDs are randomised per dial, so each number's pickup is compared with the other numbers in the same hours. Relati
- prompt_version: set in v9 at D3 11:30 by supervisor
### config v12
- welcome_message: set in v7 at D2 17:00 by controller_approved (approval apr_00008) — Promote welcome_message W2 to 85% (keep W1 at 15% as holdout)
- voice: set in v12 at D4 14:45 by controller_approved (approval apr_00012) — Test voice options V1 50%, V2 25%, V3 25%
- caller_id: set in v11 at D4 10:15 by controller_auto — rebalance load across healthy caller IDs by measured pickup (D1 0.98, D3 1.03). Caller IDs are randomised per dial, so each number's pickup is compared with the other numbers in the same hours. Relati
- prompt_version: set in v10 at D3 14:30 by controller_approved (approval apr_00010) — Revert prompt P2 -> P1: hallucination flags at 5.5% vs normal 1.4% (reverses a supervisor change made at D3 11:30)

$ python -m controller view --wf ks_cancel --db state/public_02_incidents.db
# Supervisor view — D10 00:00

## ks_cancel
Today: pickup None (yesterday 0.251), engagement None (yesterday 0.516), 0 dials

**Testing / winning**
- voice: closing, allocation {'V2': 0.62451171875, 'V3': 0.37548828125}, leading: V2 (P(best)=0.62, lift +6.1%)
- welcome_message: exploit, allocation {'W1': 0.14990234375, 'W2': 0.85009765625}, leading: W1 (P(best)=0.80, lift +0.0%)
- caller IDs: D1=healthy, D2=degraded, D3=healthy
**Waiting on you:** nothing
**Changed in the last 24h**
- nothing


$ python -m controller health --db state/public_02_incidents.db
# Controller health — last tick D10 00:00
- ingested through: D9 21:00 (lag vs last tick: 180 sim minutes)
- chunks: 491, events: 324341, ingest 51,696 events/s
- controller era: 324,341 events, ingest 6.3s + decide 59.6s over 10.0 sim days (111s wall, 11s wall per sim day)
- peak decide time per tick: 0.42s, peak RSS 216 MB
- credits: 200 → 198
- decisions: approval_requested=14, approval_approved=13, applied=12, auto_applied=9, experiment_live=9, experiment_planned=6, did_probe_healthy=5, experiment_closed=4, schedule_fit=3, experiment_winner=3, did_degraded=2, supervisor_edit=2, experiment_drop=2, approval_rejected=1, incident_opened=1, validation_run=1, incident_fix_live=1, incident_resolved=1, experiment_decay_suspected=1, experiment_decay=1, apply_stale=1, experiment_settled=1

## Recent alerts
- none
```
