"""CLI.

  python -m controller run  --url http://127.0.0.1:8700 [--db state/controller.db]
  python -m controller why  --wf nw_renewal --at "D3 14:00"     # why did this workflow change around then?
  python -m controller lead --lead nw_renewal:l00012345         # what did this customer hear, and why?
  python -m controller view [--wf ks_cancel]                    # supervisor view
  python -m controller health                                   # the loop's own health
"""
from __future__ import annotations

import argparse
import logging
import sys

DEFAULT_DB = "state/controller.db"


def main(argv=None):
    ap = argparse.ArgumentParser(prog="controller")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--url", required=True)
    r.add_argument("--db", default=DEFAULT_DB)
    r.add_argument("--no-call-log", action="store_true", help="skip the per-call audit table (faster at load)")
    w = sub.add_parser("why")
    w.add_argument("--wf", required=True)
    w.add_argument("--at", required=True, help='sim time, e.g. "D3 14:00"')
    w.add_argument("--db", default=DEFAULT_DB)
    ld = sub.add_parser("lead")
    ld.add_argument("--lead", required=True)
    ld.add_argument("--db", default=DEFAULT_DB)
    v = sub.add_parser("view")
    v.add_argument("--wf")
    v.add_argument("--db", default=DEFAULT_DB)
    v.add_argument("--json", action="store_true")
    h = sub.add_parser("health")
    h.add_argument("--db", default=DEFAULT_DB)
    a = ap.parse_args(argv)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        stream=sys.stderr)
    if a.cmd == "run":
        from .loop import Controller
        Controller(a.url, a.db, call_log=not a.no_call_log).run()
        return
    from . import report
    from .store import Store
    s = Store(a.db)
    if a.cmd == "why":
        print(report.why(s, a.wf, a.at))
    elif a.cmd == "lead":
        print(report.lead(s, a.lead))
    elif a.cmd == "view":
        print(report.view(s, a.wf, as_json=a.json))
    elif a.cmd == "health":
        print(report.health(s))


if __name__ == "__main__":
    main()
