"""Statistics used for every decision. Deterministic: the same counts always give the same answer.

Winner selection uses Beta-Binomial posteriors. Monte Carlo draws are seeded from a hash of the inputs, so a
decision can be replayed exactly from the audit store.
"""
from __future__ import annotations

import hashlib
import math

import numpy as np

PRIOR_A, PRIOR_B = 1.0, 1.0
DRAWS = 40_000


def _rng(*parts) -> np.random.Generator:
    h = hashlib.sha256(repr(parts).encode()).digest()
    return np.random.default_rng(int.from_bytes(h[:8], "little"))


def posterior_draws(arms: dict[str, tuple[int, int]], draws: int = DRAWS) -> dict[str, np.ndarray]:
    """arms: name -> (successes, trials). Returns posterior samples of each arm's rate."""
    rng = _rng(sorted(arms.items()), draws)
    return {a: rng.beta(PRIOR_A + s, PRIOR_B + max(n - s, 0), draws) for a, (s, n) in sorted(arms.items())}


def compare_arms(arms: dict[str, tuple[int, int]], incumbent: str) -> dict[str, dict]:
    """Per arm: posterior mean, P(best), P(> incumbent), relative lift vs incumbent with a 95% interval."""
    d = posterior_draws(arms)
    names = list(d)
    mat = np.vstack([d[a] for a in names])
    best = np.bincount(mat.argmax(axis=0), minlength=len(names)) / mat.shape[1]
    inc = d[incumbent]
    out = {}
    for i, a in enumerate(names):
        s, n = arms[a]
        lift = d[a] / inc - 1
        out[a] = {"succ": s, "n": n, "rate": round(s / n, 4) if n else None,
                  "mean": round(float(d[a].mean()), 4), "p_best": round(float(best[i]), 4),
                  "p_beats_incumbent": round(float((d[a] > inc).mean()), 4),
                  "lift": round(float(np.median(lift)), 4),
                  "lift_ci": [round(float(np.quantile(lift, 0.025)), 4), round(float(np.quantile(lift, 0.975)), 4)]}
    return out


def prob_greater(a: tuple[int, int], b: tuple[int, int]) -> float:
    d = posterior_draws({"a": a, "b": b})
    return float((d["a"] > d["b"]).mean())


def poisson_sf(k: int, mu: float) -> float:
    """P(X >= k) for X ~ Poisson(mu)."""
    if k <= 0:
        return 1.0
    if mu <= 0:
        return 0.0
    # sum the lower tail in log space; k is small (flag counts) so this is cheap
    term = math.exp(-mu)
    cdf = term
    for i in range(1, k):
        term *= mu / i
        cdf += term
    return max(0.0, 1.0 - cdf)


def ratio_z(observed: float, expected: float) -> float:
    """Poisson-style z for observed vs expected counts."""
    return (observed - expected) / math.sqrt(max(expected, 1e-9))


def required_n_per_arm(p: float, rel_lift: float, z_alpha: float = 1.96, z_power: float = 0.84) -> int:
    """Classic two-proportion sample size: connected calls per arm to detect a relative lift."""
    delta = p * rel_lift
    return math.ceil(2 * (z_alpha + z_power) ** 2 * p * (1 - p) / delta ** 2)
