"""Intents: what a policy module wants a workflow's config to look like, with the evidence for it.

Modules never touch the simulator. They emit intents ("set allocations.default.voice to {...} because ...");
governance decides whether that goes out as an auto-apply, a batched approval request, or waits.
Intents are plain data so they can be stored with the proposal they ended up in.
"""
from __future__ import annotations

import copy
from dataclasses import asdict, dataclass, field

AGENT_DIMS = ("welcome_message", "voice", "caller_id")


@dataclass
class Intent:
    source: str                     # module that produced it: did / schedule / experiment / incident
    path: list[str]                 # config path, e.g. ["allocations", "default", "voice"]
    value: object                   # target value at that path
    summary: str                    # one line a supervisor understands
    rationale: str
    dry_run: dict
    impact: float                   # [0,1], see governance.impact_score docs
    affected_leads: int
    evidence: dict = field(default_factory=dict)
    urgent: bool = False            # incident / safety: may use the reserved approval slot and bypass freezes
    auto: str = "prefer"            # prefer: auto-apply when policy allows; never: always ask a human
    step_ok: bool = False           # may be auto-applied in max_shift-sized steps (risk-reducing moves only)
    piggyback: bool = False         # housekeeping: never worth an approval slot on its own, rides along with others
    ref: str | None = None          # module-specific id (experiment id, incident id) for the audit trail

    @property
    def key(self) -> str:
        return ".".join(self.path)

    @property
    def dim(self) -> str:
        return dim_of(self.path)

    def to_json(self) -> dict:
        return asdict(self)


def dim_of(path: list[str]) -> str:
    if path[0] == "allocations":
        return path[2]
    if path[0] in ("prompt_version", "schedule", "cohorts"):
        return path[0]
    raise ValueError(f"unknown config path {path}")


def get_path(cfg: dict, path: list[str]):
    cur = cfg
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def apply_intents(cfg: dict, intents: list[Intent]) -> dict:
    out = copy.deepcopy(cfg)
    for it in intents:
        cur = out
        for p in it.path[:-1]:
            cur = cur.setdefault(p, {})
        cur[it.path[-1]] = copy.deepcopy(it.value)
    return out


QUANTUM = 4096


def normalise_dist(d: dict) -> dict:
    """Normalise to multiples of 1/4096 that sum to exactly 1.0 in floating point.

    The simulator re-normalises every allocation it stores (w / sum(w)) and compares distributions exactly. Weights
    that are dyadic fractions summing to exactly 1.0 are a fixed point of that, so a dimension we don't touch never
    shows up as "changed" (which would, for example, make an auto-apply touch a dimension policy forbids).
    """
    pos = {k: v for k, v in sorted(d.items()) if v > 0}
    s = sum(pos.values())
    if s <= 0:
        return {}
    raw = {k: v / s * QUANTUM for k, v in pos.items()}
    q = {k: int(v) for k, v in raw.items()}
    left = QUANTUM - sum(q.values())
    for k in sorted(raw, key=lambda k: raw[k] - q[k], reverse=True)[:left]:
        q[k] += 1
    return {k: n / QUANTUM for k, n in q.items() if n > 0}


def dist_for(cfg: dict, cohort: str, dim: str) -> dict:
    allocs = cfg.get("allocations", {})
    return normalise_dist((allocs.get(cohort) or {}).get(dim) or allocs["default"][dim])


def changed_dims(old: dict, new: dict) -> list[str]:
    """Mirror of the simulator's notion of a changed dimension (docs §4.2)."""
    out = []
    if old.get("cohorts", []) != new.get("cohorts", []):
        out.append("cohorts")
    keys = set(old.get("allocations", {})) | set(new.get("allocations", {}))
    for dim in AGENT_DIMS:
        if any(dist_for(old, k, dim) != dist_for(new, k, dim) for k in keys):
            out.append(dim)
    if old.get("prompt_version") != new.get("prompt_version"):
        out.append("prompt_version")
    if _sched(old) != _sched(new):
        out.append("schedule")
    return out


def _sched(cfg: dict) -> dict:
    s = cfg.get("schedule") or {}
    return {"hour_weights": s.get("hour_weights") or {}, "lead_preferred_hour": s.get("lead_preferred_hour") or {}}


def tv(a: dict, b: dict) -> float:
    return 0.5 * sum(abs(a.get(o, 0) - b.get(o, 0)) for o in set(a) | set(b))


def max_shift(old: dict, new: dict) -> float:
    keys = {"default"} | {c["id"] for c in old.get("cohorts", [])} | {c["id"] for c in new.get("cohorts", [])}
    return max((tv(dist_for(old, k, d), dist_for(new, k, d)) for k in keys for d in AGENT_DIMS), default=0.0)


def blend(old: dict, target: dict, alpha: float) -> dict:
    return normalise_dist({o: (1 - alpha) * old.get(o, 0) + alpha * target.get(o, 0) for o in set(old) | set(target)})


def same_value(a, b) -> bool:
    if isinstance(a, dict) and isinstance(b, dict) and all(isinstance(v, (int, float)) for v in (*a.values(), *b.values())):
        na, nb = normalise_dist(a), normalise_dist(b)
        return set(na) == set(nb) and all(abs(na[k] - nb[k]) < 1e-3 for k in na)
    return a == b
