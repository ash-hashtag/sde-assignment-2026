# Outcome-First Agent Loop — Submission

**Name:** _(fill in)_ · **Date:** 2026-11-06 · **Hours actually spent:** ~TBD · **Language / storage:** Python 3.11+ (httpx, numpy) / SQLite (WAL), no other services

---

## 0. TL;DR

- A single-process controller ingests every event exactly once into SQLite. Four policy modules (caller-ID health, hallucination incidents, welcome × voice experiments, call time) emit *intents*; one governance client turns them into auto-applies or batched approval requests, and never crosses the boundary.
- **public_01: TBD conclusions vs baseline, public_02: TBD**, with **0 harmful changes** in both. The flagged caller ID is out of rotation the same day. The supervisor's bad prompt is reverted with validation evidence in TBD. The decaying welcome message is promoted, then rolled back by its holdout.
- Crash safety is demonstrated: 8 injected crash points (each right after an unrecorded side effect) plus random SIGKILLs. There are no double-applies, no lost approvals, and every event is counted exactly once (`reports/crash_test.log`).
- Load: TBD.
- **Cut:** per-person call time, cross-tenant fairness, a UI, and prompt optimisation. Prompts are only ever *reverted* to a known-good version for safety, never tuned.

## 1. Assumptions

1. `pickup_rate_max_drop: 0.02` / `engagement_rate_max_drop: 0.02` are **absolute** drops in the rate (2 percentage points). If they were relative, the guardrails would be about half as strict; nothing in my controller is close to either bound, but the check would change.
2. Welcome message and voice are heard *after* the call connects, so they cannot move pickup. Their experiments are judged on engagement. Pickup is guarded at workflow level, and only by the levers that can move it (caller ID, schedule).
3. Scenario end (`end_minute` from `/sim/state`) is used only to avoid starting an experiment that can't finish (≥3 days left). In production this becomes "don't start one you can't exploit".
4. Supervisors' edits are authoritative. After one, the controller doesn't propose on that dimension for 48h. The one exception is a safety incident caused by the edit itself, and that proposal says plainly that it reverts a supervisor change.
5. Tenant preferences stated in memos (Kestrel: ≤2 requests/day, none before 11:00) are honoured as **voluntary** limits on top of policy, and are kept in `controller/settings.py`.
6. History before D0 ran the business default config, so it carries no evidence about any variant other than the defaults. It is used for call-time profiles, flag-rate baselines and caller-ID usage, and never as experiment evidence.
7. Hidden scenarios share the API and schema. Feature values (languages, bands) are learned from `lead` events, not hard-coded.
8. Credits: incidents may use any credits; nothing else spends them. The actual spend was 2 credits per incident (one validation of the known-good prompt).

## 2. Scope decisions

| # | Capability | Built / Partial / Cut | Why | What it would take to finish |
|---|---|---|---|---|
| C1 | Event ingestion | **Built** | Everything depends on it; load scenario is the bar | Streaming parse + COPY into Postgres in prod |
| C2 | Shared cohort object | **Partial** | One partition per workflow (age × city tier) used by schedule, reports and experiments; experiments allocate at `default` so they never fragment traffic | Data-driven partition search; segment-level allocations (see §5) |
| C3 | Bootstrapping from history | **Built** (scoped) | Call-time model, flag-rate baseline, caller-ID usage; history has no variant evidence by construction | — |
| C4 | Call-time optimisation | **Partial: per cohort** | History gives an unconfounded hour profile per segment; per-person data is too thin (2–8 attempts per person, 20–40% returning) | Per-person shrinkage for returning people via `lead_preferred_hour` |
| C5 | Caller-ID health | **Built** | Biggest pickup lever, auto-appliable on 2/3 workflows, and an incident in public_02 | Re-probe of pulled numbers after a cool-off |
| C6 | W × V experiments | **Built** | The primary KPI on most workflows | Segment-level arms (load scale makes them detectable) |
| C7 | Promotion, decay, rollback | **Built** | Holdout-based; public_02's decaying W3 is caught | — |
| C8 | Hallucination response | **Built** | Graded MTTR; regulated clients | Engagement-aware choice among several validated fixes |
| C9 | Governance client | **Built** | Every change goes through it; most failure modes live here | Approver-latency learning per tenant |
| C10 | Impact, affected leads, dry run | **Built (honest, simple)** | A ranked queue needs a meaningful score | Proper off-policy replay with propensities |
| C11 | Supervisor view | **Partial: CLI/JSON** | One screen per workflow from the store | Minimal web page on top of `view --json` |
| C12 | Audit store | **Built** | Floor requirement; `why` and `lead` queries | — |
| C13 | Crash recovery | **Built + demonstrated** | SRE non-negotiable | — |
| C14 | Loop observability | **Partial** | Metrics table + `health` command + severities on alerts | Export to Prometheus; real paging |
| C15 | Fair allocation across tenants | **Cut** | Credits never came close to binding (2 of 200 used); approver attention is already per-workflow by policy | Per-tenant credit budgets + weighted queue |

**Principle.** Build the spine that every other capability depends on first, properly: ingestion, store, governance, crash safety. Then add the levers in order of (expected lift × how much the policy lets us use them) ÷ effort. In practice that meant caller IDs, then incidents, then experiments, then call time. Anything whose main value is presentation got the thinnest version that still answers the question.

## 3. Stakeholders

### 01 — Sales (Nikhil)
- **Accepted:** speed where it is free. Caller-ID and call-time changes auto-apply within policy on the same day. Every workflow gets its first experiment request in the first approver hour of D0.
- **Declined:** a single blended score (Product and the README both forbid blending pickup and engagement). Also "winning by lunch, live by evening": at ~1,000 connected calls a day, detecting a 10% engagement lift takes 2–3 days of traffic per arm, and a lunchtime "winner" is mostly noise (see §5 false-winner table). Also rolling out the persuasive prompt everywhere.
- **Wrong claims:** *"Kestrel has turned on auto-apply for everything."* No. `ks_cancel` auto-apply covers schedule, caller ID, welcome and voice with `max_shift: 0.2`. Prompt and cohort changes always need approval. *"Northwind said auto-apply on KYC is fine."* `nw_kyc` has auto-apply **disabled**. *"Persuasive prompt tested well."* It tested in another account, and evidence must come from this workflow. P4 is also the prompt most likely to hallucinate: its validation pass rate sits right at the 0.97 bar.
- **Reply:** "Nikhil — you'll get a per-client lift number, but two of them per client: pickup and engagement, never blended. They're what Product and our clients' compliance teams have signed up to. The fast changes (caller-ID rotation, call timing) already happen same-day without a human. Changes customers *hear* need a client approval on Northwind, and calling a winner at lunch is how you end up rolling back at dinner: at our volumes a real 10% lift takes 2–3 days to see. KYC isn't on auto-apply in the signed policy, and the persuasive script doesn't go anywhere without validation on that client's own workflow."

### 02 — Northwind Compliance (Meera)
- **Accepted (all five):** every customer-facing change (welcome, voice, script) on Northwind goes through named approval. Policy already forces this, and the controller marks those intents `auto: never` regardless. Script changes carry `evidence.validation_run_id`. The `lead` query answers "why did this customer hear this", down to the variant and the change that made it live (§10). Thresholds are conservative (P(best) ≥ 0.95, holdouts, rollbacks). Requests go out only in approver hours, and only when a decision can land before expiry.
- **Pushed back:** none on substance.
- **Wrong claim:** *"call timing and caller-ID rotation are covered by the policy we signed"* is true for renewal but **not for KYC**, where auto-apply is disabled. Those changes go to their approvers on KYC.
- **Reply:** "Meera — agreed on all five. Anything a customer hears on Northwind goes to your approvers with the evidence attached, and script changes carry a validation run. One correction: the signed KYC policy doesn't allow automatic timing or caller-ID changes, so on KYC those come to you as requests too (we batch them, one a day at most). For your auditors we can answer 'why did customer X hear Y on day D' from our own records, per call, within minutes, not 24 hours. The weekly summary lists every automatic change on Renewal with its reason."

### 03 — Platform/SRE (Kabir)
- **Accepted:** kill/restart is demonstrated, not promised (`scripts/crash_test.sh`). There are idempotency keys everywhere and every side effect is written ahead. There is no new stateful infrastructure: an embedded SQLite file, with a schema that ports to the Postgres he already runs. Loop health is available without reading logs (`controller health`, metrics table). Alerts carry a severity, and only `page` ones should page.
- **Pushed back:** the "<10 wall-minutes per load day" target bundles the simulator's own generation time, which we don't control. I report both separately (§8).
- **Reply:** "Kabir — kill/restart test is in the repo: 8 injected crash points right after unrecorded side effects, plus random SIGKILLs, with checks for double-apply, lost approvals and exactly-once ingestion. No new infra: state is one SQLite file per controller, same schema as Postgres if you'd rather host it. Load numbers and what breaks at 10× are in §8. Only `severity: page` alerts should wake you, and each one names the workflow and what to look at."

### 04 — Kestrel Ops supervisor (Anita)
- **Accepted:** her edits are never undone silently. A supervisor edit locks that dimension for 48h. The one exception was her P2 script, which tripled hallucination flags. It was reverted through an approval request that says *"reverses a supervisor change made at D3 11:30"*, with the evidence attached, so she sees it before it happens. At most 2 requests a day and none before 11:00 (voluntary, stricter than policy's 4 from 10:00), with incidents exempt from the 11:00 rule. Changes on a running campaign that customers hear go to her for approval even though policy would let us auto-apply them. One screen: `controller view --wf ks_cancel`. A "strict script" fix that kills engagement is caught: after any prompt fix the controller checks engagement against the pre-incident prompt, and it prefers prompts with production history over untested ones.
- **Pushed back:** caller-ID and call-time changes still auto-apply (policy allows it, nobody hears a difference). They show up in her view under "changed in the last 24h".
- **Reply:** "Anita — your edits stand. We don't touch a setting you've changed for two days unless it's causing a safety problem, and then we *ask* you, with the evidence. We'll send at most two requests a day, never before 11:00, and anything customers hear goes through you even though your policy would let us skip that. Caller-ID rotation and call timing still happen automatically; they're on your one screen with the reason. And we check engagement after any script fix, so a 'safe' script nobody stays on gets flagged."

### 05 — Product (Tara)
- **Accepted:** KPIs stay separate everywhere. One cohort partition per workflow, shared by schedule, view and reports. Minimum sizes are chosen and justified (§5), with the speed-vs-false-winner cost measured. Every proposal carries an impact score, a diff, an affected-lead count and a dry run, and the impact score has one definition across workflows. An expired proposal is treated as a rejection and re-proposed from fresh intents, never resubmitted. Evidence comes only from calls that actually ran with an arm (the call event's own `variant`), never from what a config said. Winners stay inside their workflow.
- **Pushed back:** per-person call time as the summit headline. The data per person is too thin, so cohort-level timing ships first. Caller-ID health and the supervisor view are P0 and are in. Per-person timing is the next thing after this submission.
- **Reply:** "Tara — all the definitions are held as written; the dry run and impact score are documented in the submission so you can check they mean something. Minimum cohort size is a function of traffic, not a constant: an arm needs ~300 connected calls before any decision, which is why experiments run at workflow level and segments only become testable at load-scale volumes. Per-person timing I've deliberately left out: most people get 2–8 attempts in their life with us, which is too little to learn their hour. Cohort timing is in; per-person is next, starting with returning leads."

### 06 — CTO (Aryamann)
- **Accepted:** explainability over size (every change has a rationale and a dry run, and the `why` query works live). Hurting a cohort is worse than nothing (holdouts, rollbacks, conservative thresholds, 0 harmful changes on the public scenarios). No compute where it doesn't change a decision: no LLM call when a known-good prompt exists, 2 credits per incident. Choose, and write down who was told no.
- **Reply:** "Aryamann — I built five things properly rather than fifteen: the governance/ingestion/crash-safety spine, caller-ID health, incident response, experiments with decay rollback, and cohort call-time. I said no to blended scores, auto-promoting winners, per-person timing for now, and cross-tenant fairness. The memos had three factual errors against the enforced policies (§3); the controller follows the policies. What breaks first at 10× is in §8."

## 4. Architecture

```mermaid
flowchart LR
  subgraph SIM[simulator HTTP API]
    A[/sim/advance/] --> CH[(event chunks)]
    AP[/approvals, apply/]
    CFG[/config, auto-apply/]
    LLM[/llm, validation/]
  end
  CH -->|1 tx per chunk| ING[ingest.py]
  ING --> DB[(SQLite: aggregates, call_log,\nconfig_versions, proposals,\ndecisions, module state)]
  DB --> M1[did.py] & M2[incidents.py] & M3[experiments.py] & M4[schedule.py]
  M2 --> LLM
  M1 & M2 & M3 & M4 -->|intents| GOV[governance.py]
  GOV -->|write-ahead row| DB
  GOV --> AP & CFG
  DB --> R[report.py: why / lead / view / health]
```

- **Loop** (`loop.py`): advance (15 min while anything can happen, otherwise jump to the next active hour) → ingest new chunks → for each workflow: reconcile proposals with the simulator, collect intents from the modules, hand them to governance.
- **State:** everything lives in one SQLite file (WAL). Aggregates: pickup by (day, hour, atom, caller ID); engagement by (day, hour, atom, welcome, voice, prompt); QA by (day, hour, prompt); a per-call log for audit. Module state is JSON per (module, workflow). Proposals and decisions are append-mostly.
- **On restart:** open the DB; ingest every chunk the simulator has that the `chunks` table doesn't; reconcile every in-flight proposal against `GET /approvals` (for approvals) or config history (for auto-applies); then decide at the current minute. A fresh simulator world (new scenario, or time went backwards) archives the old DB and starts clean.

## 5. The learning loop

**Cohorts.** One partition per workflow, age band × city tier. Segments with <3% of leads fold into `default`, giving at most 12 cohorts. It is used for call timing and reporting. Experiments allocate at `default`, which every cohort inherits, so cohorts never split experiment traffic. **Minimum size** is about evidence, not leads. An arm needs ≥300 connected calls before any decision, and a two-proportion test needs ~1,300 per arm to see a 10% lift at 80% power. At dev volumes (~1,000 connects/day per workflow) only workflow-level effects are detectable within a run. At load volumes (~15k/day) a segment of ~7% of leads becomes testable in about 3 days. The cost: effects confined to a small segment (e.g. V3 for the 60+ age band) are invisible at dev scale. I accept that rather than hand out false winners.

**Experiment design.** Factorial: welcome and voice are randomised independently per dial, so one allocation tests both, and each comparison uses all traffic. Interactions in the data so far are multiplicative, so main effects are what's needed. Exploration keeps ≥50% on the incumbent with ≤25% per challenger. That bounds what an unknown bad arm can cost while it's being found out. All exploration and promotion goes to a human, even where policy would allow auto-apply. Only calls that actually ran with an arm count, and only from when the allocation went live.

**Deciding a winner.** Beta(1,1)–Binomial posterior per arm on engaged/connected. Promote when P(best) ≥ 0.95 *and* P(beats incumbent) ≥ 0.975 *and* every arm has ≥300 connects *and* the last 24h still agree (P(beats) ≥ 0.6 on the recent window), so a winner that is already fading isn't promoted. P(best) over all arms is the multiple-comparison control: one decision per dimension, not one test per arm. Arms with P(beats incumbent) ≤ 0.025, overall or on the trailing 36h, are dropped. If nothing reaches the bar in 4 days, traffic settles in proportion to P(best) among arms more likely than not to beat the incumbent. No winner is declared then, and nothing is reverted to an option the data says is worse. Posterior draws are seeded from a hash of the counts, so decisions are deterministic and replayable. **False-winner rate** (Monte Carlo of the exact rule, `scripts/false_winner.py`, evaluated every dialling hour): TBD.

**Decay and rollback.** Promotion keeps 15% on the previous option as a holdout. Every tick, the trailing 36h of winner vs holdout is checked; P(winner worse) ≥ 0.9 triggers an urgent rollback, which auto-applies in max_shift steps where policy allows and otherwise uses the reserved approval slot. In public_02, W3 (+18%, decaying from day 2) was promoted, then rolled back. Its share fell to 0 by day 5 after onset.

**Call time and caller ID.** Call time: history ran a flat schedule, so pickup by (segment, hour) there is unconfounded. Each cohort's hour weight is its comparative advantage (pickup in h ÷ its own daily mean)^γ, with cells shrunk toward a segment × hour product model and every hour kept above 0.2 so no capacity is wasted. γ ∈ {1,2,3} is picked by an IPF dry run that keeps hourly capacity and per-cohort attempts fixed. Predicted lift is +1.6–2.2% pickup. Per-person timing was cut (§2). Caller ID: per-dial randomisation makes "this number vs the other numbers in the same hours" a clean test. A number is pulled when its ratio is <0.5, z < −4, *and* it's a change from its own previous 12h. Untested numbers are probed at 5% (one at a time where auto-apply allows). Healthy numbers share traffic ∝ (measured health)², shrunk by significance, at most every 6h. This captures that busy numbers pick up worse: it was the largest single lever (e.g. nw_kyc went from one number to three).

**Guardrail KPI.** The levers are split by which KPI they can move. W/V can't change pickup, so for engagement-primary workflows the pickup guardrail is threatened only by caller ID and schedule, and both are chosen to *raise* pickup. For nw_kyc (pickup primary), W/V experiments are the engagement guardrail's own lever, and they are only promoted on engagement gains. Workflow-level pickup and engagement are visible day-on-day in the view, and every `why` answer shows 24h before/after.

## 6. Governance

**State machine:**
```
submitting ─POST ok→ pending ─→ approved ─apply ok→ applied
    │                   │          ├─409 stale→ stale     → intents re-proposed on the new base next slot
    │                   │          ├─410──────→ lapsed    → re-proposed
    │                   │          └─urgent in flight→ deferred (left to lapse; re-proposed after)
    │                   ├─→ rejected → intents come back next slot with fresh data
    │                   └─→ expired  → treated as rejection; never resubmitted as-is
    ├─4xx→ refused (alert)
    └─crash→ reconciled on restart (found in /approvals → adopt; not found → abandoned)
auto: submitting → applied | refused (reconciled from config history after a crash)
```

**Batching and timing.** At most one non-urgent approval in flight per workflow. Everything the modules want that needs a human goes into it. The quota is `min(policy, tenant preference)` per 24h with one slot reserved for incidents, and requests are spaced ≥3h apart. A request is only sent inside approver hours, and only if its decision can land before expiry (same-day, or next-day opening within the TTL), so nothing sits in a night queue. Approved changes are applied on the next tick (15 min), well inside the 2h apply window.

**Auto-apply vs voluntary restraint.** Auto-apply is used for caller ID and schedule where policy allows. It is never used for anything a customer hears, except rollbacks (risk-reducing; stepped within `max_shift`). Promotions are never chained in max_shift-sized steps to get around the limit. Auto-applies are frozen while an approval is in flight, because any version bump would make it stale. Safety moves (pulling a degraded number) ignore the freeze and accept the re-proposal cost.

**Impact score, affected leads, dry run.** Impact score = 1 − exp(−x / (2% of the daily batch)), where x = expected extra concluded leads per day. A change worth 2% of a day's leads scores 0.63 and one worth 5% scores 0.92, on every workflow, so a queue ranked by it is ranked by expected outcome. Exploration has expected value ≈ 0 and scores ≈ 0: its value is information, and the rationale says so. Incidents are floored at 0.9. Affected leads: active (uploaded within the cadence, not concluded) for mid-flight changes, the next batch for `next_campaign_only`. Dry runs: experiments use posterior means of arms *that ran* replayed over the last 3 days' connected volume (arms with no evidence are shown as such, assumed equal to the incumbent). Caller ID uses hour-matched health × the new allocation. Schedule uses the IPF redistribution of history. Prompt changes use production flag rates plus the validation run. These are honest about what they are: model-based estimates, not off-policy replays with propensities.

**Supervisor edits mid-experiment.** The edit is recorded as a decision. That dimension's experiment stops ("their choice stands"), its data is kept, and no proposals touch the dimension for 48h. Any in-flight approval that the edit made stale is detected on apply (409) and re-proposed from fresh intents on the new base. In public_02, the nw_renewal voice change at D5 15:00 stopped the voice experiment, and the 48h lock ran past the point where a new one could finish, so it was left alone.

## 7. Incidents

**Detection.** Hallucination flags on the *current* prompt over 1h, 3h and 12h windows vs the workflow's historical flag rate (which includes the detector's ~1% false-positive floor). Fire when flags ≥ 8, ≥2× normal and Poisson tail p < 1e-4. For 24h after any prompt change the bar is ≥6 flags and p < 1e-3, because that's where regressions come from. Expected false positives: per check, ≤1e-4 (≤1e-3 after a change). With ~150 correlated checks per workflow-day, that is well under one false incident per workflow-month outside change windows.

**Fix.** Cheapest first: a prompt with production history on this workflow and a normal flag rate (usually the one before the incident) → validate it (n=200, 2 credits) → propose as urgent with `evidence.validation_run_id`. Only if no such prompt exists, ask the LLM (3 credits) and validate its suggestions in turn. After apply, verify flags return to normal on ≥150 connects and engagement isn't significantly down vs the reference prompt; otherwise page.

**public_02 timeline (ks_cancel):** TBD.

## 8. Scale

TBD.

## 9. Reliability

- **Method** (`scripts/crash_test.sh`, log in `reports/crash_test.log`): `CONTROLLER_CRASHPOINTS` makes the process `os._exit` (no cleanup, like SIGKILL) at 8 points: mid-ingest before commit; after an auto-apply PUT, before an approval POST and after it; after an apply POST (several of them on later occurrences). Then 4 random SIGKILLs. Then run to completion and verify against the simulator: no approval or auto-apply applied twice, every simulator approval known to the store with the same status, nothing lapsed unintentionally, every chunk ingested once, and aggregate dial counts equal to the raw call events. **All checks pass.**
- **State lost on crash:** at most the in-progress tick's decisions that hadn't been written. They are recomputed identically, because modules are functions of the store and proposal ids are deterministic (`{wf}-{kind}-{minute}-v{base}-{config hash}`).
- **Idempotency keys:** chunk number (ingestion), `proposal_id` (approvals and auto-applies, written before the call), `approval_id` status guard (apply), `event_id` (call log, sim events).
- **4xx/5xx:** transport errors and 5xx retry with exponential backoff (all calls are reads or carry their own idempotency key). 4xx are returned as values: 409 stale → `stale` and re-propose; 410 → `lapsed`; 403 auto-apply → recorded, intent falls to the approval path; 402 credits → page; any unexpected 4xx → `alert`.

## 10. Audit & observability

TBD (real outputs).

**Alerts.** Page: a module crashed (workflow left unchanged); an apply failed unexpectedly; no validated fix exists for an open incident; a fix didn't bring flags down; out of credits. Ticket (business hours): auto-apply refused; approval request refused; a safe fix that lowered engagement. Don't alert: rejections, expiries, stale bases (normal governance; visible in the view), probes and rebalances.

## 11. Results

TBD.

## 12. Trade-offs & rejected alternatives

| Option | Why considered | Why rejected / what instead |
|---|---|---|
| Thompson sampling with continuous re-allocation | Faster regret | Every re-allocation is an approval on Northwind; fixed allocations per approval + Bayesian stopping |
| Frequentist sequential test (alpha spending) | Classic, auditors know it | Posterior statements ("P it's best") read better to a supervisor; peeking handled by conservative bars + measured false-winner rate |
| Promote winners to 100% | Captures the full lift | No way to see decay; 15% holdout costs ~2% of the lift and buys rollback |
| Per-person call time | Product headline | Too few observations per person; cohort timing ships first |
| `lead_preferred_hour` per person from feature model, auto-applied | Avoids needing cohort approval | Same information as cohort weights, a 6MB config at load scale every day, and invisible to a supervisor |
| Chaining auto-applies in max_shift steps for promotions | Faster on Kestrel | Defeats the intent of max_shift; only risk-reducing moves are stepped |
| LLM first for every incident | Matches the C8 sketch | Spends credits where a known-good revert is the obvious, better-evidenced fix |
| Postgres / Redis | SRE already runs them | Embedded SQLite keeps `run.sh` dependency-free; schema is portable |
| Store raw events | Full replay | Aggregates + compact call log are enough for every question asked; ~10× smaller |

## 13. Known weaknesses

TBD.

## 14. If this went to production at Formi next month

TBD.
