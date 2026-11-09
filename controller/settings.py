"""Tunables and stakeholder-agreed preferences, in one place so they can be argued about in review.

Policy (what the simulator enforces) comes from the API. Everything here is a *voluntary* constraint on top of
policy, or a statistical threshold; SUBMISSION.md explains each choice.
"""

# Voluntary governance preferences per tenant, on top of the enforced policy.
# kestrel_finance: their ops supervisor asked for at most 2 requests a day and nothing before 11:00 (memo 04).
TENANT_PREFS = {
    "kestrel_finance": {"max_requests_per_day": 2, "earliest_request_hour": 11},
}

# Governance
RESERVED_URGENT_SLOTS = 1          # approval slots per workflow per 24h kept free for incidents
MIN_HOURS_BETWEEN_REQUESTS = 3     # non-urgent requests per workflow are spaced out

# Experiments (welcome_message, voice)
EXPLORE_INCUMBENT_SHARE = 0.5      # the current option keeps at least half the traffic while challengers are tested
MAX_CHALLENGER_SHARE = 0.25        # ... and no single untested option gets more than this
MIN_DAYS_LEFT_TO_EXPLORE = 3.0     # exploration only pays if there is time left to use what it finds
MIN_CONN_PER_ARM = 300             # connected calls per arm before any decision
P_BEST_TO_PROMOTE = 0.95           # posterior probability the challenger is the best arm
P_BEATS_INCUMBENT = 0.975          # ... and that it beats the incumbent
P_LOSER_DROP = 0.025               # arms this unlikely to beat the incumbent are dropped at the next request
P_RECENT_LOSER_DROP = 0.05         # ... or this unlikely over the trailing DECAY_WINDOW_HOURS (fading arms)
MAX_EXPLORE_DAYS = 4.0             # after this many days live, stop exploring and keep the best-supported arm
HOLDOUT_SHARE = 0.20               # after promotion the previous option keeps this share, to detect decay
P_DECAY_ROLLBACK = 0.90            # posterior P(winner < holdout) on the trailing window ...
                                   # (scripts/decay_monitor_sim.py: 20%/0.9/2 catches 86% of decays,
                                   #  4.7% false rollback of a real +5% winner; 15%/0.95/2 caught 54%)
DECAY_CONFIRMATIONS = 2            # ... on this many consecutive checks ...
DECAY_CHECK_EVERY_HOURS = 6        # ... spaced this far apart (a real decay persists, noise doesn't)
DECAY_WINDOW_HOURS = 36            # trailing window (dialling hours count, wall-clock hours of sim time)
MIN_HOLDOUT_CONN = 120
STALE_PROMOTION_HOURS = 12         # a promotion not live this long after its decision is re-checked on recent data
SUPERVISOR_LOCK_HOURS = 48         # after a supervisor edits a dimension we leave it alone this long

# Caller ID health
DID_WINDOW_HOURS = 6               # trailing dialling hours used for health
DID_DEGRADED_RATIO = 0.5           # pickup ratio vs the other caller IDs below which a number in use is pulled
DID_DEGRADED_Z = -4.0              # ... and the deficit must be this significant (population, not anecdote)
DID_PROBE_SHARE = 0.05             # share given to an untested caller ID while it is evaluated
DID_PROBE_MIN_DIALS = 250          # dials on a probe before an ambiguous one is judged
DID_PROBE_EARLY_DIALS = 120        # ... a clearly healthy or clearly bad one can be judged from this many
DID_REBALANCE_MIN_TV = 0.1         # don't churn the allocation for small differences
DID_REBALANCE_EVERY_HOURS = 6

# Hallucination incidents
QA_WINDOWS_HOURS = (1, 3, 12)      # short window catches a sudden spike, long one a slow rise
QA_MIN_FLAGS = 10
QA_P_VALUE = 1e-6                  # Poisson tail vs the workflow's normal flag rate, when no prompt changed
                                   # (~150 correlated looks/day/workflow: 1e-4 produced a false incident on public_02)
QA_MIN_RATIO = 2.0
QA_MIN_FLAGS_RECENT = 6            # within 24h of a prompt change
QA_P_VALUE_RECENT = 1e-3
VALIDATION_N = 200                 # 2 credits; enough to separate ~1% from ~5% failure rates
CREDIT_FLOOR_SHARE = 0.25          # never spend below this share of the starting credits except for incidents

# Call time
SCHEDULE_GAMMA = 2.0               # sharpening of relative hour preference
SCHEDULE_MIN_WEIGHT = 0.2
SCHEDULE_MIN_SEGMENT_SHARE = 0.03  # segments smaller than this fold into default
SCHEDULE_REFIT_HOURS = 24
