"""Monte Carlo of the decay monitor: false rollbacks of a real winner vs time to catch a fading one.

Hourly traffic (12 dialling hours/day), winner/holdout split, checks at 09:00 and 15:00 on a trailing window,
rollback after N consecutive checks with P(winner < holdout) >= threshold — the rule in experiments._monitor.

    python scripts/decay_monitor_sim.py [runs] [connects_per_day]
"""
import sys

import numpy as np

from controller.stats import compare_arms

RUNS = int(sys.argv[1]) if len(sys.argv) > 1 else 150
CONN = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
BASE, DAYS, WINDOW_H = 0.55, 7, 36


def lift_at(t_h, scenario):
    if scenario == "real +5%":
        return 0.05
    d = t_h / 24  # decays from +15% to -10% over two days starting day 2 (like public W3)
    return 0.15 if d < 2 else max(-0.10, 0.15 - 0.25 * (d - 2) / 2)


def run(rng, holdout, p_thr, confirm, scenario):
    hist = []  # (abs hour, w_eng, w_n, h_eng, h_n)
    streak = 0
    for day in range(DAYS):
        for hour in range(9, 21):
            t = day * 24 + hour
            n = rng.poisson(CONN / 12)
            nh = rng.binomial(n, holdout)
            nw = n - nh
            pw = min(BASE * (1 + lift_at(t, scenario)), 0.95)
            hist.append((t, rng.binomial(nw, pw), nw, rng.binomial(nh, BASE), nh))
            if hour in (9, 15) and day >= 1:
                rows = [r for r in hist if r[0] > t - WINDOW_H]
                w = (sum(r[1] for r in rows), sum(r[2] for r in rows))
                h = (sum(r[3] for r in rows), sum(r[4] for r in rows))
                if h[1] < 120:
                    continue
                res = compare_arms({"w": w, "h": h}, "h")
                streak = streak + 1 if 1 - res["w"]["p_beats_incumbent"] >= p_thr else 0
                if streak >= confirm:
                    return t / 24
    return None


def main():
    rng = np.random.default_rng(11)
    print(f"{RUNS} runs, {CONN} connected/day, {WINDOW_H}h window, checks 09:00 & 15:00")
    print("| holdout | P(worse) bar | confirmations | false rollback of a +5% winner (7 days) | decay caught | median day caught (decay starts D2, crosses 0 ~D3.2) |")
    print("|---|---|---|---|---|---|")
    for holdout, p_thr, confirm in [(0.15, 0.95, 2), (0.15, 0.9, 2), (0.2, 0.9, 2), (0.25, 0.9, 2), (0.2, 0.95, 1), (0.25, 0.95, 2)]:
        fa = [run(rng, holdout, p_thr, confirm, "real +5%") for _ in range(RUNS)]
        de = [run(rng, holdout, p_thr, confirm, "decay") for _ in range(RUNS)]
        caught = [d for d in de if d is not None]
        print(f"| {holdout:.0%} | {p_thr} | {confirm} | {sum(x is not None for x in fa) / RUNS:.1%} | "
              f"{len(caught) / RUNS:.0%} | {np.median(caught):.1f} |" if caught else "| — |")


if __name__ == "__main__":
    main()
