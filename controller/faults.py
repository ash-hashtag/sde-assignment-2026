"""Deterministic crash injection for the crash-recovery test.

CONTROLLER_CRASHPOINTS="after_approval_post:2,mid_ingest:5" makes the process die (os._exit, like SIGKILL: no
cleanup, no flush) the 2nd time it reaches `after_approval_post`, or the 5th time it reaches `mid_ingest`.
Unset in normal runs, where `crashpoint` is a dictionary lookup and nothing else.
"""
import os

_spec = {k: int(v) for k, v in (p.split(":") for p in os.environ.get("CONTROLLER_CRASHPOINTS", "").split(",") if p)}
_hits: dict[str, int] = {}


def crashpoint(name: str):
    if name in _spec:
        _hits[name] = _hits.get(name, 0) + 1
        if _hits[name] == _spec[name]:
            print(f"crashpoint {name} hit #{_hits[name]}: exiting", flush=True)
            os._exit(137)
