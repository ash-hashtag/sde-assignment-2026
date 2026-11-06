"""Policy modules. Each reads the store and emits intents; none of them talks to governance directly."""
from .did import DidHealth
from .experiments import Experiments
from .incidents import Incidents
from .schedule import Schedule


def build_modules(store, client):
    # order matters only for readability of the audit trail: safety first
    return [Incidents(store, client), DidHealth(store, client), Experiments(store, client), Schedule(store, client)]
