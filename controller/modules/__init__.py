"""Policy modules. Each reads the store and emits intents; none of them talks to governance directly."""
from .did import DidHealth
from .experiments import Experiments
from .incidents import Incidents
from .schedule import Schedule


def build_modules(store, client):
    """CONTROLLER_MODULES=did,incidents (comma list) runs a subset: for ablations and for switching a lever off in an
    emergency without a deploy. Default: all."""
    import os
    every = {"incidents": Incidents, "did": DidHealth, "experiments": Experiments, "schedule": Schedule}
    wanted = [m for m in os.environ.get("CONTROLLER_MODULES", ",".join(every)).split(",") if m]
    # order matters only for readability of the audit trail: safety first
    return [every[m](store, client) for m in every if m in wanted]
