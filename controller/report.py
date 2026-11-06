"""Read-only views over the store: audit ("why"), per-customer trace, supervisor view, loop health.

Everything here reads only the controller's own SQLite file; nothing comes from the simulator's logs.
"""
from __future__ import annotations

import json
from collections import Counter

from .simtime import MIN_PER_DAY, fmt, parse
from .store import Store


def _j(s):
    return json.loads(s) if s else None


def _kpi(s: Store, wf: str, lo: int, hi: int) -> dict:
    """Pickup and engagement for calls in sim minutes [lo, hi), from hourly aggregates."""
    a, b = lo // 60, hi // 60
    dials, conn = s.q("SELECT COALESCE(SUM(dials),0), COALESCE(SUM(conn),0) FROM agg_pick WHERE wf=? "
                      "AND day>=? AND day*24+hour>=? AND day*24+hour<?", (wf, a // 24, a, b))[0]
    c2, eng, flags = s.q("SELECT COALESCE(SUM(conn),0), COALESCE(SUM(eng),0), COALESCE(SUM(flags),0) FROM agg_qa "
                         "WHERE wf=? AND day>=? AND day*24+hour>=? AND day*24+hour<?", (wf, a // 24, a, b))[0]
    return {"dials": dials, "pickup": round(conn / dials, 3) if dials else None,
            "engagement": round(eng / c2, 3) if c2 else None,
            "halluc_flag_rate": round(flags / c2, 4) if c2 else None}


def why(s: Store, wf: str, at: str) -> str:
    t = parse(at)
    out = [f"# Why did {wf} change around {fmt(t)}?", ""]
    rows = s.q("SELECT version, actor, changed_dims, applied_minute, proposal_id, approval_id FROM config_versions "
               "WHERE wf=? AND applied_minute IS NOT NULL AND applied_minute BETWEEN ? AND ? ORDER BY version",
               (wf, t - 6 * 60, t + 60))
    if not rows:
        prev = s.q("SELECT version, actor, changed_dims, applied_minute, proposal_id, approval_id FROM config_versions "
                   "WHERE wf=? AND applied_minute IS NOT NULL AND applied_minute<=? ORDER BY version DESC LIMIT 1",
                   (wf, t))
        out.append("No change in the 6h before / 1h after. Version live at that time:" if prev else
                   "No controller-era change before that time; the business default config was live.")
        rows = prev
    for version, actor, dims, applied, pid, aid in rows:
        out += [f"## v{version} at {fmt(applied)} — {actor}, changed {', '.join(_j(dims) or [])}", ""]
        if actor == "supervisor":
            out.append("Edited directly by the client's supervisor (bypasses governance). Controller response:")
            for m, kind, summ in s.q("SELECT minute, kind, summary FROM decisions WHERE wf=? AND minute BETWEEN ? AND ? "
                                     "AND kind IN ('supervisor_edit','incident_opened','experiment_closed') ORDER BY id",
                                     (wf, applied, applied + 12 * 60)):
                out.append(f"- {fmt(m)} {kind}: {summ}")
        p = s.q("SELECT path, request, intents, created_minute, decided_minute, status, approval_id FROM proposals "
                "WHERE proposal_id=?", (pid,)) if pid else []
        if p:
            path, req, intents, created, decided, status, paid = p[0]
            req, intents = _j(req), _j(intents)
            if path == "approval":
                ev = s.q("SELECT body FROM sim_events WHERE type='approval_decided' AND body LIKE ?", (f'%"{aid}"%',))
                dec = _j(ev[0][0]) if ev else {}
                out += [f"**Proposal** `{pid}` requested {fmt(created)}, approval `{aid}` "
                        f"{dec.get('status', status)} by the client approver at {dec.get('ts', '?')[11:16]}, "
                        f"applied {fmt(applied)}.",
                        f"- Summary: {req['change_summary']}",
                        f"- Impact score {req['impact_score']}, affected leads {req['affected_leads']}",
                        f"- Diff: `{json.dumps(req['diff'], default=str)[:600]}`",
                        f"- Rationale: {req['rationale']}",
                        f"- Evidence: {json.dumps(req.get('evidence') or {})}"]
            else:
                out += [f"**Auto-applied** `{pid}` under the workflow's auto-apply policy (no human approval needed "
                        f"for {', '.join(_j(dims) or [])}).", f"- Rationale: {req['rationale']}"]
            for it in intents:
                out.append(f"- Dry run ({it['key'] if 'key' in it else '.'.join(it['path'])}): "
                           f"`{json.dumps(it['dry_run'], default=str)[:500]}`")
            refs = {it.get("ref") for it in intents if it.get("ref")}
            for ref in sorted(refs):
                trail = s.q("SELECT minute, kind, summary FROM decisions WHERE wf=? AND ref=? ORDER BY id", (wf, ref))
                if trail:
                    out += ["", f"**Decision trail for {ref}:**"]
                    out += [f"- {fmt(m)} {k}: {sm}" for m, k, sm in trail]
        before, after = _kpi(s, wf, applied - MIN_PER_DAY, applied), _kpi(s, wf, applied, applied + MIN_PER_DAY)
        out += ["", f"**What happened next** (24h before → 24h after): pickup {before['pickup']} → {after['pickup']}, "
                    f"engagement {before['engagement']} → {after['engagement']}, hallucination flags "
                    f"{before['halluc_flag_rate']} → {after['halluc_flag_rate']}"]
        nxt = s.q("SELECT minute, kind, summary FROM decisions WHERE wf=? AND minute>? AND minute<=? AND kind IN "
                  "('experiment_decay','incident_resolved','did_degraded','applied','auto_applied','alert',"
                  "'experiment_winner','experiment_drop') ORDER BY id LIMIT 8", (wf, applied, applied + 2 * MIN_PER_DAY))
        out += [f"- {fmt(m)} {k}: {sm}" for m, k, sm in nxt]
        out.append("")
    return "\n".join(out)


def lead(s: Store, lead_id: str) -> str:
    calls = s.q("SELECT minute, attempt, config_version, cohort, wm, voice, did, prompt, connected, engaged, wf "
                "FROM call_log WHERE lead_id=? ORDER BY minute", (lead_id,))
    if not calls:
        return f"No controller-era calls recorded for {lead_id}."
    wf = calls[0][10]
    out = [f"# What {lead_id} heard ({wf})", ""]
    for m, att, ver, coh, wm, voice, did, pr, conn, eng, _ in calls:
        outcome = "engaged" if eng else "connected, dropped" if conn else "not connected"
        out.append(f"- {fmt(m)} attempt {att}: welcome {wm}, voice {voice}, caller ID {did}, prompt {pr}, "
                   f"cohort {coh}, config v{ver} → {outcome}")
    out += ["", "## Why those variants were live",
            "For each config version the customer was dialled under, the change that last set each dimension:"]
    for ver in sorted({c[2] for c in calls}):
        out.append(f"### config v{ver}")
        for dim in ("welcome_message", "voice", "caller_id", "prompt_version"):
            r = s.q("SELECT version, actor, applied_minute, proposal_id, approval_id FROM config_versions WHERE wf=? "
                    "AND version<=? AND changed_dims LIKE ? ORDER BY version DESC LIMIT 1", (wf, ver, f'%"{dim}"%'))
            if not r:
                out.append(f"- {dim}: business default configuration (never changed before v{ver})")
                continue
            v, actor, applied, pid, aid = r[0]
            req = _j(s.q1("SELECT request FROM proposals WHERE proposal_id=?", (pid,))) if pid else None
            line = f"- {dim}: set in v{v} at {fmt(applied)} by {actor}" + (f" (approval {aid})" if aid else "")
            if req:
                line += f" — {req.get('change_summary') or req.get('rationale', '')[:200]}"
            out.append(line)
    return "\n".join(out)


def view(s: Store, wf: str | None = None, as_json: bool = False) -> str:
    """The supervisor's one screen: what's being tested, what's winning, what we want from you, what changed."""
    now = s.meta_get("last_minute", 0)
    wfs = [wf] if wf else [r[0] for r in s.q("SELECT wf FROM workflows ORDER BY wf")]
    data = {}
    for w in wfs:
        today = now - now % MIN_PER_DAY
        exps = (s.state_get("experiments", w) or {}).get("exps", {})
        dids = (s.state_get("did", w) or {}).get("dids", {})
        inc = (s.state_get("incidents", w) or {}).get("open")
        pending = s.q("SELECT approval_id, created_minute, request FROM proposals WHERE wf=? AND status IN "
                      "('pending','approved')", (w,))
        changes = s.q("SELECT minute, kind, summary FROM decisions WHERE wf=? AND minute>=? AND kind IN "
                      "('applied','auto_applied','supervisor_edit') ORDER BY id", (w, today - MIN_PER_DAY))
        alerts = s.q("SELECT minute, summary, detail FROM decisions WHERE wf=? AND kind='alert' AND minute>=? "
                     "ORDER BY id", (w, now - MIN_PER_DAY))
        data[w] = {
            "kpis_today": _kpi(s, w, today, now + 60), "kpis_yesterday": _kpi(s, w, today - MIN_PER_DAY, today),
            "experiments": {d: {"phase": e["phase"], "incumbent": e["incumbent"], "allocation": e["target"],
                                "leader": _leader(e)} for d, e in exps.items()},
            "caller_ids": {d: i["status"] for d, i in dids.items()},
            "incident": inc and {"id": inc["id"], "phase": inc["phase"], "bad_prompt": inc["bad_prompt"],
                                 "fix": inc.get("fix")},
            "waiting_on_you": [{"approval": a, "since": fmt(c), "summary": _j(r)["change_summary"],
                                "impact": _j(r)["impact_score"]} for a, c, r in pending],
            "changes_last_24h": [f"{fmt(m)} {k}: {sm}" for m, k, sm in changes],
            "alerts_last_24h": [f"{fmt(m)} [{(_j(d) or {}).get('severity', '?')}] {sm}" for m, sm, d in alerts],
        }
    if as_json:
        return json.dumps(data, indent=2, default=str)
    out = [f"# Supervisor view — {fmt(now)}", ""]
    for w, d in data.items():
        k, y = d["kpis_today"], d["kpis_yesterday"]
        out += [f"## {w}",
                f"Today: pickup {k['pickup']} (yesterday {y['pickup']}), engagement {k['engagement']} "
                f"(yesterday {y['engagement']}), {k['dials']} dials", ""]
        out.append("**Testing / winning**")
        for dim, e in d["experiments"].items():
            out.append(f"- {dim}: {e['phase']}, allocation {e['allocation']}" + (f", leading: {e['leader']}" if e["leader"] else ""))
        out.append(f"- caller IDs: " + ", ".join(f"{k_}={v}" for k_, v in sorted(d["caller_ids"].items())))
        if d["incident"]:
            out.append(f"- **open incident** {d['incident']}")
        out.append("**Waiting on you**" if d["waiting_on_you"] else "**Waiting on you:** nothing")
        for p in sorted(d["waiting_on_you"], key=lambda p: -p["impact"]):
            out.append(f"- {p['approval']} (impact {p['impact']}, since {p['since']}): {p['summary']}")
        out.append("**Changed in the last 24h**")
        out += [f"- {c}" for c in d["changes_last_24h"]] or ["- nothing"]
        if d["alerts_last_24h"]:
            out.append("**Alerts**")
            out += [f"- {a}" for a in d["alerts_last_24h"]]
        out.append("")
    return "\n".join(out)


def _leader(e: dict) -> str | None:
    arms = (e.get("last_eval") or {}).get("arms")
    if not arms:
        return None
    best = max(arms, key=lambda a: arms[a]["p_best"])
    return f"{best} (P(best)={arms[best]['p_best']:.2f}, lift {arms[best]['lift']:+.1%})"


def health(s: Store) -> str:
    """The loop's own health for on-call: ingest throughput and lag, decision volume, credit burn, alerts."""
    rows = s.q("SELECT minute, wall, events, ingest_sec, decide_sec, credits, proposals, rss_mb FROM metrics "
               "ORDER BY minute")
    if not rows:
        return "no metrics yet"
    ev = sum(r[2] for r in rows)
    ing = sum(r[3] for r in rows)
    dec = sum(r[4] for r in rows)
    sim_days = (rows[-1][0] - rows[0][0]) / MIN_PER_DAY or 1
    wall = rows[-1][1] - rows[0][1]
    lag = s.q1("SELECT MAX(until_minute) FROM chunks")
    kinds = Counter(k for (k,) in s.q("SELECT kind FROM decisions WHERE minute>=0"))
    alerts = s.q("SELECT minute, wf, summary, detail FROM decisions WHERE kind='alert' ORDER BY id DESC LIMIT 10")
    hist = s.q("SELECT COUNT(*), SUM(events), SUM(ingest_sec) FROM chunks")[0]
    out = [f"# Controller health — last tick {fmt(rows[-1][0])}",
           f"- ingested through: {fmt(lag) if lag is not None else '-'} (lag vs last tick: "
           f"{(rows[-1][0] - lag) if lag is not None else '-'} sim minutes)",
           f"- chunks: {hist[0]}, events: {hist[1]}, ingest {hist[1] / max(hist[2], 1e-9):,.0f} events/s",
           f"- controller era: {ev:,} events, ingest {ing:.1f}s + decide {dec:.1f}s over {sim_days:.1f} sim days "
           f"({wall:.0f}s wall, {wall / sim_days:.0f}s wall per sim day)",
           f"- peak decide time per tick: {max(r[4] for r in rows):.2f}s, peak RSS {max(r[7] for r in rows):.0f} MB",
           f"- credits: {rows[0][5]:.0f} → {rows[-1][5]:.0f}",
           f"- decisions: " + ", ".join(f"{k}={v}" for k, v in kinds.most_common()),
           "", "## Recent alerts"]
    out += [f"- {fmt(m)} {wf} [{(_j(d) or {}).get('severity', '?')}] {sm}" for m, wf, sm, d in alerts] or ["- none"]
    return "\n".join(out)
