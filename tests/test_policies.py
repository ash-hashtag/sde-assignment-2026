"""Policy-module decisions on synthetic evidence: each test pins a behaviour a seed sweep or variant run caught going
wrong (see SUBMISSION.md section 11). The store is real; the evidence is hand-written aggregate rows."""
import json

import pytest

from controller import settings as S
from controller.ctx import WorkflowCtx
from controller.modules.did import DidHealth
from controller.modules.experiments import Experiments
from controller.stats import compare_arms
from controller.store import Store

WF = "wf1"
DAY = 1440
SPEC = {"tenant_id": "t", "governance": {"auto_apply": {"enabled": False}}, "dialling_window": [9, 21],
        "mid_flight": "allowed", "daily_batch": {"size": 1000}, "cadence": [0, 1, 2],
        "objective": {"primary": "engagement_rate"},
        "options": {"welcome_message": ["W1", "W2", "W3"], "voice": ["V1"], "caller_id": ["D1", "D2", "D3"],
                    "prompt_version": ["P1"]}}


@pytest.fixture()
def store(tmp_path):
    return Store(tmp_path / "c.db")


def ctx(store, now, wm=None):
    cfg = {"allocations": {"default": {"welcome_message": wm or {"W1": 1.0}, "voice": {"V1": 1.0}}},
           "prompt_version": "P1", "cohorts": [], "schedule": {}}
    return WorkflowCtx(wf=WF, spec=SPEC, config=cfg, version=3, now=now, store=store)


def eng(store, minute, arm, conn, engaged):
    """Connected and engaged calls for one welcome-message arm in the dialling hour containing `minute`."""
    d, h = divmod(minute // 60, 24)
    store.db.execute("INSERT INTO agg_eng VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT DO UPDATE SET "
                     "conn = conn + excluded.conn, eng = eng + excluded.eng", (WF, d, h, 0, arm, "V1", "P1", conn, engaged))


def explore_exp(live_since, incumbent="W1", arms=("W1", "W2", "W3")):
    return {"id": "exp-t", "dim": "welcome_message", "phase": "explore", "incumbent": incumbent, "arms": list(arms),
            "dropped": {}, "decayed": [], "target": {}, "live_since": live_since}


# ---------------------------------------------------------------- settling an undecided test

def test_settle_leaves_out_an_arm_that_is_losing_recently(store):
    m, now = Experiments(store, None), 5 * DAY + 15 * 60
    # all time: W2 well ahead (an early burst); last 36h: W2 clearly behind W1 (it is fading)
    eng(store, 1 * DAY + 12 * 60, "W1", 600, 300)
    eng(store, 1 * DAY + 12 * 60, "W2", 600, 420)
    eng(store, 1 * DAY + 12 * 60, "W3", 600, 305)
    eng(store, now - 3 * 60, "W1", 400, 200)
    eng(store, now - 3 * 60, "W2", 400, 150)
    eng(store, now - 3 * 60, "W3", 400, 202)
    exp = explore_exp(DAY)
    counts = m._arm_counts(ctx(store, now), "welcome_message", DAY)
    m._close(ctx(store, now), exp, counts, "test", compare_arms(counts, "W1"))
    assert "W2" not in exp["target"]


def test_settle_away_from_incumbent_keeps_a_holdout_and_is_then_watched_for_decay(store):
    m, now = Experiments(store, None), 5 * DAY + 15 * 60
    for t in (1 * DAY + 12 * 60, now - 3 * 60):        # W2 ahead both all-time and recently, but not by a winner's bar
        eng(store, t, "W1", 400, 200)
        eng(store, t, "W2", 400, 222)
    exp = explore_exp(DAY, arms=("W1", "W2"))
    counts = m._arm_counts(ctx(store, now), "welcome_message", DAY)
    m._close(ctx(store, now), exp, counts, "test", compare_arms(counts, "W1"))
    assert max(exp["target"], key=exp["target"].get) == "W2"
    assert exp["target"]["W1"] >= S.HOLDOUT_SHARE - 1e-3
    assert exp["watch"] == {"winner": "W2", "holdout": "W1"}
    # once the settle is live, the experiment monitors it like a promotion
    st = {"exps": {"welcome_message": exp}, "seq": 1}
    assert m._dim(ctx(store, now + 60, wm=exp["target"]), st, "welcome_message") is None
    assert exp["phase"] == "exploit" and exp["winner"] == "W2" and exp["holdout"] == "W1"


def test_a_material_settle_is_its_own_request_a_reweighting_rides_along(store):
    m, now = Experiments(store, None), 5 * DAY + 15 * 60
    eng(store, 2 * DAY + 12 * 60, "W1", 1000, 500)
    eng(store, 2 * DAY + 12 * 60, "W2", 1000, 560)
    exp = {**explore_exp(DAY, arms=("W1", "W2")), "phase": "closing", "piggyback": True,
           "last_eval": {"arms": compare_arms({"W1": (500, 1000), "W2": (560, 1000)}, "W1")}}
    exp["target"] = {"W1": 0.2, "W2": 0.8}
    material = m._intent(ctx(store, now, wm={"W1": 0.5, "W2": 0.5}), exp, {"W1": 0.5, "W2": 0.5})
    assert not material.piggyback
    exp["target"] = {"W1": 0.49, "W2": 0.51}
    small = m._intent(ctx(store, now, wm={"W1": 0.5, "W2": 0.5}), exp, {"W1": 0.5, "W2": 0.5})
    assert small.piggyback


# ---------------------------------------------------------------- re-checking a promotion that isn't live yet

def promoted_exp(decided):
    return {"id": "exp-t", "dim": "welcome_message", "phase": "exploit", "incumbent": "W1", "arms": ["W1", "W2"],
            "dropped": {}, "decayed": [], "winner": "W2", "holdout": "W1", "promoted_decision": decided,
            "live_since": None, "target": {"W2": 0.8, "W1": 0.2},
            "evidence": {"W2": {"lift": 0.1, "lift_ci": [0.01, 0.2], "n": 300, "p_best": 0.98, "mean": 0.55}}}


def test_no_recheck_while_the_promotion_waits_for_the_approver(store):
    m, decided = Experiments(store, None), 4 * DAY + 16 * 60
    now = decided + (S.STALE_PROMOTION_HOURS + 4) * 60
    eng(store, now - 3 * 60, "W1", 300, 150)
    eng(store, now - 3 * 60, "W2", 300, 120)          # recent window even points against W2
    store.db.execute("INSERT INTO proposals (proposal_id, wf, path, status, urgent, base_version, dims, intents, "
                     "request, config, created_minute) VALUES ('p1', ?, 'approval', 'pending', 0, 3, '[]', ?, '{}', "
                     "'{}', ?)", (WF, json.dumps([{"source": "experiment", "ref": "exp-t"}]), decided))
    exp = promoted_exp(decided)
    m._dim(ctx(store, now, wm={"W1": 0.75, "W2": 0.25}), {"exps": {"welcome_message": exp}, "seq": 1},
           "welcome_message")
    assert exp["phase"] == "exploit" and exp["winner"] == "W2"


@pytest.mark.parametrize("w2_engaged, withdrawn", [(100, False), (80, True)])   # neutral keeps; contrary withdraws
def test_recheck_withdraws_only_when_recent_evidence_points_against(store, w2_engaged, withdrawn):
    m, decided = Experiments(store, None), 4 * DAY + 16 * 60
    now = decided + (S.STALE_PROMOTION_HOURS + 4) * 60
    eng(store, now - 3 * 60, "W1", 200, 100)
    eng(store, now - 3 * 60, "W2", 200, w2_engaged)
    exp = promoted_exp(decided)
    m._dim(ctx(store, now, wm={"W1": 0.75, "W2": 0.25}), {"exps": {"welcome_message": exp}, "seq": 1},
           "welcome_message")
    assert (exp["phase"] == "explore") is withdrawn
    assert ("W2" in exp["decayed"]) is withdrawn


# ---------------------------------------------------------------- caller-ID probes

@pytest.mark.parametrize("ratio, dials, z, verdict", [
    (0.85, 260, -1.2, "probing"),     # 85% of loaded peers while barely used: not good enough, not yet bad
    (0.85, 800, -2.0, "degraded"),    # ... and with plenty of data it is out
    (0.97, 130, -0.2, "healthy"),     # clearly fine: judged early
    (0.92, 260, -0.8, "healthy"),
    (0.60, 130, -3.5, "degraded"),
])
def test_probe_must_read_close_to_its_loaded_peers(store, monkeypatch, ratio, dials, z, verdict):
    m, now = DidHealth(store, None), 3 * DAY + 14 * 60
    monkeypatch.setattr(m, "_stats", lambda c, hours, **kw: {"D3": {"dials": dials, "conn": 0, "expected": 50.0,
                                                                   "ratio": ratio, "z": z, "other_dials": 5000}})
    dids = {"D3": {"status": "probing", "since": now - 20 * 60}}
    m._judge_probes(ctx(store, now), dids)
    assert dids["D3"]["status"] == verdict
