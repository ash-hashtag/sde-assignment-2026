# Grade report — public_02_incidents

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.357 | +44.2% | 0.253 | +37.8% | 0.484 | +1.7% | 16% | 455 (330) |
| nw_kyc | 0.446 | +19.1% | 0.288 | +18.9% | 0.588 | -0.8% | 5% | 40 (31) |
| nw_renewal | 0.502 | +17.6% | 0.295 | +12.5% | 0.566 | +3.2% | 15% | 63 (55) |
| ALL | 0.424 | +26.9% | 0.274 | +23.5% | 0.536 | +1.1% | 14% | 558 (416) |

## Changes applied by the controller

23 applied — neutral: 8, beneficial: 15

- ks_cancel v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.006 → **neutral**
- nw_renewal v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.006 → **neutral**
- nw_renewal v3 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=+0.032 didΔ=+0.000 → **beneficial**
- ks_cancel v3 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=+0.017 didΔ=+0.000 → **beneficial**
- nw_kyc v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'caller_id', 'schedule'] engageΔ=-0.010 didΔ=+0.042 → **beneficial**
- ks_cancel v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.031 → **beneficial**
- nw_renewal v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.008 → **neutral**
- ks_cancel v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.014 → **neutral**
- nw_renewal v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.032 → **beneficial**
- nw_renewal v6 (controller_approved) dims=['welcome_message'] engageΔ=+0.093 didΔ=+0.000 → **beneficial**
- nw_renewal v7 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.024 → **beneficial**
- ks_cancel v6 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.164 → **beneficial**
- ks_cancel v7 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.082 → **beneficial**
- nw_renewal v8 (controller_approved) dims=['voice'] engageΔ=+0.018 didΔ=+0.000 → **beneficial**
- nw_renewal v9 (controller_approved) dims=['voice'] engageΔ=-0.006 didΔ=+0.000 → **neutral**
- nw_renewal v10 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- ks_cancel v9 (controller_approved) dims=['welcome_message'] engageΔ=+0.026 didΔ=+0.000 → **beneficial**
- nw_kyc v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.235 → **beneficial**
- nw_renewal v11 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.001 → **neutral**
- ks_cancel v10 (controller_approved) dims=['voice'] engageΔ=+0.002 didΔ=+0.000 → **neutral**
- nw_kyc v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.036 didΔ=+0.000 → **beneficial**
- nw_kyc v5 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.033 → **beneficial**
- nw_renewal v13 (controller_approved) dims=['welcome_message'] engageΔ=+0.086 didΔ=+0.000 → **beneficial**

## Governance

```
{
  "approval_requests": 14,
  "decisions": {
    "approved": 14,
    "expired": 0
  },
  "rejection_reasons": {},
  "applied_via_approval": 13,
  "auto_applied": 10,
  "auto_apply_rejected": 0,
  "apply_conflicts": 1,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nw_kyc": 2,
    "nw_renewal": 2,
    "ks_cancel": 1
  }
}
```

## Incidents

```
[
  {
    "type": "did_flagged",
    "workflow": "ks_cancel",
    "at": "D2 10:00",
    "flagged_did_share_by_day": {
      "2": 0.056,
      "3": 0.0,
      "4": 0.0,
      "5": 0.0,
      "6": 0.0,
      "7": 0.0,
      "8": 0.0,
      "9": 0.0
    }
  },
  {
    "type": "supervisor_edit",
    "workflow": "ks_cancel",
    "at": "D3 11:30",
    "mttr_minutes": null,
    "fixed_by": null
  },
  {
    "type": "supervisor_edit",
    "workflow": "nw_renewal",
    "at": "D5 15:00"
  }
]
```

## Decaying variants — share of in-population calls still on the variant, by day after onset

```
{
  "nw_renewal:welcome_message=W3": {
    "2": 0.803,
    "3": 0.794,
    "4": 0.803,
    "5": 0.796,
    "6": 0.249,
    "7": 0.0,
    "8": 0.0,
    "9": 0.0
  }
}
```

Credits used: 0 · validation runs: 0 · LLM fix calls: 0