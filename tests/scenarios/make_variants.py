"""Builds "hidden-like" scenario variants to test the controller on truth it was never tuned on.

Same schema as the public scenarios; different hidden effects, caller-ID health, incidents and governance policy.
These files are test fixtures for the simulator only — the controller never reads them (it can't: it only talks HTTP).

    python tests/scenarios/make_variants.py      # writes tests/scenarios/variant_*.yaml
"""
import copy
from pathlib import Path

import yaml

HERE = Path(__file__).parent
ROOT = HERE.parent.parent


def load(name):
    return yaml.safe_load((ROOT / "scenarios" / name).read_text())


def wf(sc, wid):
    return next(w for t in sc["tenants"] for w in t["workflows"] if w["id"] == wid)


def variant_a():
    """Incidents the public scenarios don't have; policies tighter; winners and decays elsewhere."""
    sc = copy.deepcopy(load("public_02_incidents.yaml"))
    sc.update(name="variant_a", seed=707, days=9)
    # a bad untested caller ID on the approval-only workflow; a flag on a different workflow
    wf(sc, "nw_kyc")["did_base_health"] = {"D2": 0.5}
    wf(sc, "nw_renewal")["did_base_health"] = {}
    # Kestrel approvers: narrower hours, slower, fewer requests, short TTL
    g = wf(sc, "ks_cancel")["governance"]
    g.update(approver_hours=[12, 17], approver_latency_minutes=[60, 300], max_requests_per_24h=2,
             proposal_ttl_hours=8)
    sc["effects"] = [
        {"workflow": "nw_renewal", "dim": "welcome_message", "value": "W2", "mult": 1.12},
        {"workflow": "nw_renewal", "dim": "voice", "value": "V4", "mult": 1.15,
         "decay": {"after_exposure_days": 2, "to_mult": 0.88, "over_days": 1.5}},
        {"workflow": "nw_renewal", "dim": "voice", "value": "V2", "mult": 0.90},
        {"workflow": "nw_kyc", "dim": "welcome_message", "value": "W2", "mult": 1.10, "where": {"lang": ["en"]}},
        {"workflow": "nw_kyc", "dim": "voice", "value": "V2", "mult": 0.90},
        {"workflow": "ks_cancel", "dim": "welcome_message", "value": "W3", "mult": 1.12,
         "where": {"age_band": ["18-30", "31-45"]}},
        {"workflow": "ks_cancel", "dim": "voice", "value": "V2", "mult": 0.88},
        {"workflow": "ks_cancel", "dim": "welcome_message", "value": "W2", "mult": 1.10,
         "decay": {"after_exposure_days": 2, "to_mult": 0.92, "over_days": 2}},
    ]
    sc["incidents"] = [
        {"type": "did_flagged", "workflow": "nw_renewal", "did": "D1", "at": "D4 11:00", "base_health": 0.4},
        # the "persuasive" prompt: passes validation (~0.972 vs 0.97) but hallucinates 4x more in production
        {"type": "supervisor_edit", "workflow": "ks_cancel", "at": "D2 14:00", "patch": {"prompt_version": "P4"},
         "note": "supervisor ships the persuasive script"},
        {"type": "supervisor_edit", "workflow": "nw_kyc", "at": "D3 12:00",
         "patch": {"allocations": {"default": {"voice": {"V2": 1}}}}, "note": "supervisor forces a voice"},
    ]
    return sc


def variant_b():
    """Different shapes: no-effect workflow (A/A), tight credits, late-evening incident, odd auto-apply policies."""
    sc = copy.deepcopy(load("public_01_dev.yaml"))
    sc.update(name="variant_b", seed=909, days=8, credits=20)
    r = wf(sc, "nw_renewal")
    r.update(language_mix={"hi": 0.3, "ta": 0.2, "mr": 0.2, "te": 0.3}, dialling_window=[10, 19], cadence=[3, 3],
             did_base_health={})
    r["governance"]["auto_apply"] = {"enabled": True, "allowed_dims": ["schedule"], "max_shift": 0.3}
    k = wf(sc, "nw_kyc")
    k["governance"]["auto_apply"] = {"enabled": True, "allowed_dims": ["caller_id", "schedule"], "max_shift": 0.3}
    c = wf(sc, "ks_cancel")
    c["options"]["prompt_version"] = ["P1", "P2", "P3", "P4"]
    sc["prompts"]["P2"] = {"summary": "Supervisor edit: adds payment-urgency language and benefit claims",
                           "halluc": 0.055, "engage_mult": 0.93}
    sc["effects"] = [
        # nw_kyc: no effects at all -> any promotion there is a false winner
        {"workflow": "nw_renewal", "dim": "voice", "value": "V3", "mult": 1.20, "where": {"lang": ["ta", "mr"]}},
        {"workflow": "nw_renewal", "dim": "welcome_message", "value": "W3", "mult": 0.85},
        {"workflow": "ks_cancel", "dim": "welcome_message", "value": "W2", "mult": 1.15},
        {"workflow": "ks_cancel", "dim": "voice", "value": "V4", "mult": 0.85},
    ]
    sc["incidents"] = [
        {"type": "did_flagged", "workflow": "ks_cancel", "did": "D1", "at": "D1 09:30", "base_health": 0.3},
        # a safe-but-dull prompt from a supervisor: not a hallucination incident; their call
        {"type": "supervisor_edit", "workflow": "nw_renewal", "at": "D2 11:00", "patch": {"prompt_version": "P5"}},
        # a bad prompt shipped after the approvers' day is nearly over
        {"type": "supervisor_edit", "workflow": "ks_cancel", "at": "D5 18:30", "patch": {"prompt_version": "P2"}},
    ]
    return sc


def main():
    for name, sc in (("variant_a", variant_a()), ("variant_b", variant_b())):
        out = HERE / f"{name}.yaml"
        out.write_text(yaml.safe_dump(sc, sort_keys=False))
        print("wrote", out)


if __name__ == "__main__":
    main()
