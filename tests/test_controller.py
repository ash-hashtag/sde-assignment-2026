"""Controller tests. The controller itself never imports `sim`; tests do, to drive a real world in-process and to
check our mirror of the simulator's contract (e.g. changed_dims) against the real thing."""
import copy
import json

import pytest

from controller import intents as I
from controller import stats
from controller.client import ApiResult
from controller.ctx import WorkflowCtx
from controller.governance import Governance
from controller.ingest import Ingestor
from controller.intents import Intent
from controller.simtime import Clock
from controller.store import Store
from sim.scenario import load_scenario
from sim.world import ApiError, World, changed_dims as sim_changed_dims, normalise_config


class WorldClient:
    """SimClient look-alike over an in-process World, so tests run the real governance rules without HTTP."""

    def __init__(self, world: World):
        self.w = world

    def _wrap(self, fn, *a):
        try:
            return ApiResult(200, fn(*a))
        except ApiError as e:
            return ApiResult(e.status, {"error": e.code, "detail": e.detail})

    def get(self, path, **params):
        w = self.w
        if path == "/approvals":
            return self._wrap(w.list_approvals, params.get("workflow_id"), params.get("status"))
        if path.startswith("/approvals/"):
            return self._wrap(w.get_approval, path.split("/")[2])
        if path.endswith("/config/history"):
            return self._wrap(w.config_history, path.split("/")[2])
        if path.endswith("/config"):
            return self._wrap(w.get_config, path.split("/")[2])
        raise NotImplementedError(path)

    def post(self, path, body):
        if path == "/approvals":
            return self._wrap(self.w.request_approval, body)
        if path.endswith("/apply"):
            return self._wrap(self.w.apply_approval, path.split("/")[2], body["approval_id"])
        if path == "/sim/advance":
            return self._wrap(self.w.advance, body["minutes"])
        raise NotImplementedError(path)

    def put(self, path, body):
        return self._wrap(self.w.auto_apply, path.split("/")[2], body)

    def must(self, r):
        assert r.ok, r.body
        return r.body

    def state(self):
        return self.w.state()

    def workflows(self):
        return [self.w.workflow_public(wid) for wid in self.w.wfs]

    def config(self, wid):
        return self.w.get_config(wid)

    def config_history(self, wid):
        return self.w.config_history(wid)

    def chunks(self, kind, after):
        return [c for c in self.w.chunks if c["kind"] == kind and c["chunk"] > after]

    def chunk_events(self, n):
        path = self.w.run_dir / self.w.chunks[n]["path"]
        return (json.loads(l) for l in path.read_text().splitlines() if l)


@pytest.fixture()
def world(tmp_path):
    sc = load_scenario("scenarios/public_01_dev.yaml")
    sc["days"], sc["history_days"] = 3, 2
    return World(sc, tmp_path / "run")


@pytest.fixture()
def store(tmp_path):
    return Store(tmp_path / "c.db")


def ctx_for(world, store, wid, client):
    cur = client.config(wid)
    return WorkflowCtx(wf=wid, spec=world.workflow_public(wid), config=cur["config"], version=cur["version"],
                       now=world.now, store=store)


def voice_intent(value, **kw):
    return Intent(source="test", path=["allocations", "default", "voice"], value=value, summary="s", rationale="r",
                  dry_run={"x": 1}, impact=0.1, affected_leads=10, **kw)


# ---------------------------------------------------------------- contract mirrors
def test_normalised_dist_is_a_fixed_point_of_the_simulators_normalisation():
    for raw in ({"V1": 0.5, "V2": 1 / 6, "V3": 1 / 6, "V4": 1 / 6}, {"a": 1, "b": 2, "c": 7}, {"x": 0.3333}):
        d = I.normalise_dist(raw)
        s = float(sum(d.values()))
        assert s == 1.0
        assert {k: float(v) / s for k, v in d.items()} == d


def test_changed_dims_matches_simulator(world):
    spec = world.wfs["nw_renewal"].spec
    old = normalise_config(spec, world.get_config("nw_renewal")["config"])
    new = copy.deepcopy(old)
    new["allocations"]["default"]["voice"] = I.normalise_dist({"V1": 1, "V2": 1})
    new["cohorts"] = [{"id": "young", "where": {"age_band": ["18-30"]}}]
    new["schedule"]["hour_weights"] = {"young": {"18": 2.0}}
    new = normalise_config(spec, new)
    assert I.changed_dims(old, new) == sim_changed_dims(old, new)


def test_auto_apply_of_one_dim_does_not_touch_others(world, store):
    """Regression: re-sending the simulator's own floats must not register as a change on other dims."""
    c = WorldClient(world)
    world.advance(600)
    ctx = ctx_for(world, store, "nw_renewal", c)
    cfg = copy.deepcopy(ctx.config)
    cfg["allocations"]["default"]["voice"] = I.normalise_dist({"V1": 3, "V2": 1, "V3": 1, "V4": 1})
    world._apply(world.wfs["nw_renewal"], normalise_config(world.wfs["nw_renewal"].spec, cfg), "supervisor", None, None)
    ctx = ctx_for(world, store, "nw_renewal", c)
    gov = Governance(store, c)
    it = Intent(source="did", path=["allocations", "default", "caller_id"], value={"D1": 0.5, "D2": 0.45, "D3": 0.05},
                summary="probe", rationale="r", dry_run={"x": 1}, impact=0.1, affected_leads=1)
    gov.act(ctx, [it])
    row = store.q("SELECT status, dims FROM proposals")[0]
    assert row[0] == "applied" and json.loads(row[1]) == ["caller_id"]


# ---------------------------------------------------------------- stats
def test_compare_arms_is_deterministic():
    arms = {"W1": (300, 600), "W2": (340, 600), "W3": (290, 600)}
    assert stats.compare_arms(arms, "W1") == stats.compare_arms(dict(reversed(list(arms.items()))), "W1")


def test_poisson_tail():
    assert stats.poisson_sf(0, 3.0) == 1.0
    assert abs(stats.poisson_sf(1, 2.0) - (1 - 2.718281828 ** -2)) < 1e-6
    assert stats.poisson_sf(20, 3.0) < 1e-8


# ---------------------------------------------------------------- governance
def test_request_apply_and_idempotent_reconcile(world, store):
    c = WorldClient(world)
    gov = Governance(store, c)
    world.advance(600)                      # D0 10:00, approvers working
    ctx = ctx_for(world, store, "nw_renewal", c)
    gov.act(ctx, [voice_intent({"V1": 0.5, "V2": 0.5})])
    (pid, status, aid), = store.q("SELECT proposal_id, status, approval_id FROM proposals")
    assert status == "pending" and aid
    a = world.approvals[aid]
    a["_decision"], a["_reasons"], a["decide_minute"] = "approved", [], world.now
    world.advance(15)                       # decision lands; we are inside the apply window
    for _ in range(3):                      # reconciling repeatedly applies exactly once
        gov.reconcile(ctx_for(world, store, "nw_renewal", c))
    applied = [v for v in world.config_history("nw_renewal") if v["approval_id"] == aid]
    assert len(applied) == 1
    assert store.q1("SELECT status FROM proposals WHERE proposal_id=?", (pid,)) == "applied"


def test_lapsed_when_apply_window_missed(world, store):
    c = WorldClient(world)
    gov = Governance(store, c)
    world.advance(600)
    gov.act(ctx_for(world, store, "nw_renewal", c), [voice_intent({"V1": 0.5, "V2": 0.5})])
    aid = store.q1("SELECT approval_id FROM proposals")
    a = world.approvals[aid]
    a["_decision"], a["_reasons"], a["decide_minute"] = "approved", [], world.now
    world.advance(4 * 60)                   # we were away longer than apply_window_hours
    gov.reconcile(ctx_for(world, store, "nw_renewal", c))
    assert store.q1("SELECT status FROM proposals") == "lapsed"
    assert not [v for v in world.config_history("nw_renewal") if v["approval_id"] == aid]


def test_crash_after_post_is_recovered(world, store):
    """Simulate a crash between POST /approvals and recording its result: the row stays 'submitting'."""
    c = WorldClient(world)
    world.advance(600)
    ctx = ctx_for(world, store, "nw_renewal", c)
    gov = Governance(store, c)
    gov.act(ctx, [voice_intent({"V1": 0.5, "V2": 0.5})])
    store.db.execute("UPDATE proposals SET status='submitting', approval_id=NULL")
    gov.reconcile(ctx)
    status, aid = store.q("SELECT status, approval_id FROM proposals")[0]
    assert status == "pending" and aid == world.list_approvals("nw_renewal", None)[0]["approval_id"]
    # and nothing is re-submitted for the same intent while it is in flight
    gov.act(ctx, [voice_intent({"V1": 0.5, "V2": 0.5})])
    assert store.q1("SELECT COUNT(*) FROM proposals") == 1


def test_stale_on_supervisor_edit_then_reproposed(world, store):
    c = WorldClient(world)
    gov = Governance(store, c)
    world.advance(600)
    ctx = ctx_for(world, store, "nw_renewal", c)
    gov.act(ctx, [voice_intent({"V1": 0.5, "V2": 0.5})])
    w = world.wfs["nw_renewal"]
    cfg = copy.deepcopy(w.current["config"])
    cfg["prompt_version"] = "P3"
    world._apply(w, cfg, "supervisor", None, None)     # supervisor edit while our request is pending
    a = world.approvals["apr_00001"]
    a["_decision"], a["decide_minute"] = "approved", world.now
    world.advance(15)
    gov.reconcile(ctx_for(world, store, "nw_renewal", c))
    assert store.q1("SELECT status FROM proposals") == "stale"
    assert world.get_config("nw_renewal")["config"]["prompt_version"] == "P3"   # not overwritten


def test_quota_keeps_a_slot_for_incidents(world, store):
    c = WorldClient(world)
    gov = Governance(store, c)
    world.advance(600)
    ctx = ctx_for(world, store, "nw_kyc", c)            # max 2 requests / 24h
    ok, _ = gov.can_request_now(ctx, urgent=False)
    assert ok
    store.db.execute("INSERT INTO proposals (proposal_id, wf, path, status, approval_id, created_minute) "
                     "VALUES ('x', 'nw_kyc', 'approval', 'rejected', 'apr_x', ?)", (world.now,))
    assert not gov.can_request_now(ctx, urgent=False)[0]
    assert gov.can_request_now(ctx, urgent=True)[0]


def test_auto_apply_frozen_while_approval_in_flight(world, store):
    c = WorldClient(world)
    gov = Governance(store, c)
    world.advance(600)
    ctx = ctx_for(world, store, "nw_renewal", c)
    gov.act(ctx, [voice_intent({"V1": 0.5, "V2": 0.5})])
    did = Intent(source="did", path=["allocations", "default", "caller_id"], value={"D1": 0.4, "D2": 0.4, "D3": 0.2},
                 summary="rebalance", rationale="r", dry_run={"x": 1}, impact=0.1, affected_leads=1)
    gov.act(ctx_for(world, store, "nw_renewal", c), [did])
    assert store.q1("SELECT COUNT(*) FROM proposals WHERE path='auto'") == 0
    did.urgent, did.step_ok = True, True                # safety moves are not frozen
    gov.act(ctx_for(world, store, "nw_renewal", c), [did])
    assert store.q1("SELECT status FROM proposals WHERE path='auto'") == "applied"


def test_max_shift_stepping_for_risk_reducing_moves(world, store):
    c = WorldClient(world)
    gov = Governance(store, c)
    world.advance(600)
    ctx = ctx_for(world, store, "ks_cancel", c)         # max_shift 0.2
    it = Intent(source="did", path=["allocations", "default", "caller_id"], value={"D1": 1.0},
                summary="pull D2", rationale="r", dry_run={"x": 1}, impact=0.9, affected_leads=1,
                urgent=True, step_ok=True)
    gov.act(ctx, [it])
    d = world.get_config("ks_cancel")["config"]["allocations"]["default"]["caller_id"]
    assert abs(d["D2"] - 0.3) < 0.01


# ---------------------------------------------------------------- ingestion
def test_ingest_is_exactly_once(world, store):
    c = WorldClient(world)
    ing = Ingestor(store, c, Clock.from_state(world.state()))
    n1, _, _ = ing.ingest_all()
    world.advance(1440)
    n2, _, _ = ing.ingest_all()
    assert n1 > 0 and n2 > 0
    assert ing.ingest_all()[0] == 0                       # nothing new
    meta = world.chunks[-1]
    assert ing.ingest_chunk(meta)[0] == 0                 # replaying a committed chunk is a no-op
    calls = sum(1 for ch in world.chunks for l in (world.run_dir / ch["path"]).read_text().splitlines()
                if '"type":"call"' in l)
    assert store.q1("SELECT SUM(dials) FROM agg_pick") == calls
