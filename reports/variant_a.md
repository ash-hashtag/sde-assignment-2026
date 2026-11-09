# Grade report — variant_a

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.390 | +9.0% | 0.268 | +11.6% | 0.502 | -2.5% | -33% | 105 (195) |
| nw_kyc | 0.384 | +8.6% | 0.253 | +4.0% | 0.583 | +3.3% | -43% | 30 (25) |
| nw_renewal | 0.509 | +46.7% | 0.288 | +31.9% | 0.594 | +7.9% | 36% | 53 (42) |
| ALL | 0.429 | +21.3% | 0.272 | +16.6% | 0.550 | +2.6% | 7% | 188 (262) |

## Changes applied by the controller

18 applied — neutral: 6, beneficial: 10, harmful: 2

- ks_cancel v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.006 → **neutral**
- nw_renewal v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.006 → **neutral**
- nw_renewal v3 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=+0.038 didΔ=+0.000 → **beneficial**
- ks_cancel v3 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=+0.022 didΔ=+0.000 → **beneficial**
- nw_kyc v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'caller_id', 'schedule'] engageΔ=-0.011 didΔ=+0.015 → **harmful**
- nw_renewal v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.007 → **neutral**
- ks_cancel v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.030 → **beneficial**
- nw_renewal v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.052 → **beneficial**
- ks_cancel v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.013 → **neutral**
- nw_renewal v6 (controller_approved) dims=['welcome_message'] engageΔ=+0.063 didΔ=+0.000 → **beneficial**
- nw_renewal v7 (controller_approved) dims=['voice'] engageΔ=+0.101 didΔ=+0.000 → **beneficial**
- nw_renewal v8 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.002 → **neutral**
- nw_renewal v9 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.010 → **neutral**
- ks_cancel v7 (controller_approved) dims=['prompt_version'] engageΔ=-0.048 didΔ=+0.000 → **harmful**
- nw_renewal v10 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.162 → **beneficial**
- ks_cancel v8 (controller_approved) dims=['voice'] engageΔ=+0.020 didΔ=+0.000 → **beneficial**
- nw_renewal v11 (controller_approved) dims=['voice'] engageΔ=+0.105 didΔ=+0.000 → **beneficial**
- nw_kyc v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.054 didΔ=+0.000 → **beneficial**

## Governance

```
{
  "approval_requests": 12,
  "decisions": {
    "approved": 10,
    "rejected": 1,
    "expired": 0
  },
  "rejection_reasons": {
    "approver declined (judgement call)": 1
  },
  "applied_via_approval": 9,
  "auto_applied": 9,
  "auto_apply_rejected": 0,
  "apply_conflicts": 1,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "nw_kyc": 1,
    "nw_renewal": 2,
    "ks_cancel": 1
  }
}
```

## Incidents

```
[
  {
    "type": "supervisor_edit",
    "workflow": "ks_cancel",
    "at": "D2 14:00",
    "mttr_minutes": 1440,
    "fixed_by": "controller_approved"
  },
  {
    "type": "supervisor_edit",
    "workflow": "nw_kyc",
    "at": "D3 12:00"
  },
  {
    "type": "did_flagged",
    "workflow": "nw_renewal",
    "at": "D4 11:00",
    "flagged_did_share_by_day": {
      "4": 0.068,
      "5": 0.0,
      "6": 0.0,
      "7": 0.0,
      "8": 0.0
    }
  }
]
```

## Decaying variants — share of in-population calls still on the variant, by day after onset

```
{
  "nw_renewal:voice=V4": {
    "2": 0.702,
    "3": 0.797,
    "4": 0.641,
    "5": 0.0,
    "6": 0.0,
    "7": 0.0,
    "8": 0.0
  },
  "ks_cancel:welcome_message=W2": {
    "2": 0.259,
    "3": 0.247,
    "4": 0.249,
    "5": 0.242,
    "6": 0.251,
    "7": 0.25,
    "8": 0.246
  }
}
```

Credits used: 4 · validation runs: 2 · LLM fix calls: 0