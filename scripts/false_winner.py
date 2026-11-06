"""Monte Carlo of the experiment decision rule: false-winner rate (A/A) and power / time-to-decision (A/B).

Mirrors controller.modules.experiments: explore allocation (incumbent >= 50%, challengers <= 25% each), evaluation
every dialling hour, promotion at P(best) >= 0.95 and P(beats incumbent) >= 0.975 with >= 300 connected calls per
arm, loser drop at P(beats) <= 0.025, give up after 4 days.

    python scripts/false_winner.py [runs] [connects_per_day]
"""
import sys

import numpy as np

from controller import settings as S
from controller.modules.experiments import Experiments
from controller.stats import compare_arms

RUNS = int(sys.argv[1]) if len(sys.argv) > 1 else 200
CONN_PER_DAY = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
HOURS_PER_DAY = 12
BASE = 0.55


def run_one(rng, lifts: dict[str, float]) -> tuple[str | None, float]:
    """Returns (promoted arm or None, days to decision)."""
    arms = list(lifts)
    inc = arms[0]
    target = Experiments._explore_target(None, inc, arms[1:])
    counts = {a: [0, 0] for a in arms}
    dropped = set()
    for hour in range(int(S.MAX_EXPLORE_DAYS * HOURS_PER_DAY)):
        n = rng.poisson(CONN_PER_DAY / HOURS_PER_DAY)
        live = {a: p for a, p in target.items() if a not in dropped}
        names = list(live)
        probs = np.array([live[a] for a in names]) / sum(live.values())
        alloc = rng.multinomial(n, probs)
        for a, k in zip(names, alloc):
            counts[a][1] += k
            counts[a][0] += rng.binomial(k, min(BASE * (1 + lifts[a]), 0.95))
        cur = {a: tuple(counts[a]) for a in names}
        if any(c[1] < S.MIN_CONN_PER_ARM for c in cur.values()):
            continue
        res = compare_arms(cur, inc)
        best = max(res, key=lambda a: res[a]["p_best"])
        if best != inc and res[best]["p_best"] >= S.P_BEST_TO_PROMOTE and \
                res[best]["p_beats_incumbent"] >= S.P_BEATS_INCUMBENT:
            return best, (hour + 1) / HOURS_PER_DAY
        for a in names:
            if a != inc and res[a]["p_beats_incumbent"] <= S.P_LOSER_DROP:
                dropped.add(a)
        if len(dropped) == len(arms) - 1 or res[inc]["p_best"] >= S.P_BEST_TO_PROMOTE:
            return None, (hour + 1) / HOURS_PER_DAY
    return None, S.MAX_EXPLORE_DAYS


def main():
    rng = np.random.default_rng(7)
    cases = {
        "A/A, 3 arms": {"W1": 0, "W2": 0, "W3": 0},
        "A/A, 4 arms": {"V1": 0, "V2": 0, "V3": 0, "V4": 0},
        "one arm +10%, 3 arms": {"W1": 0, "W2": 0.10, "W3": 0},
        "one arm +15%, 3 arms": {"W1": 0, "W2": 0.15, "W3": 0},
        "one arm +15%, 4 arms": {"V1": 0, "V2": 0, "V3": 0.15, "V4": 0},
        "one arm -10%, 2 arms": {"W1": 0, "W2": -0.10},
    }
    print(f"{RUNS} runs per case, {CONN_PER_DAY} connected calls/day, base engagement {BASE}")
    print("| case | promoted a non-best arm | promoted the best arm | median days to promotion |")
    print("|---|---|---|---|")
    for name, lifts in cases.items():
        best = max(lifts, key=lifts.get) if max(lifts.values()) > 0 else None
        out = [run_one(rng, lifts) for _ in range(RUNS)]
        wrong = sum(1 for a, _ in out if a is not None and a != best) / RUNS
        right = sum(1 for a, _ in out if a is not None and a == best) / RUNS
        days = [d for a, d in out if a is not None and a == best]
        print(f"| {name} | {wrong:.1%} | {right:.1%} | {np.median(days):.1f} |" if days else
              f"| {name} | {wrong:.1%} | {right:.1%} | — |")


if __name__ == "__main__":
    main()
