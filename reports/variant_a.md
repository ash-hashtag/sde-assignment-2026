# Grade report — variant_a

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.400 | +11.6% | 0.265 | +10.6% | 0.520 | +0.9% | -7% | 87 (195) |
| nw_kyc | 0.401 | +13.3% | 0.268 | +10.0% | 0.574 | +1.7% | -35% | 32 (25) |
| nw_renewal | 0.494 | +42.3% | 0.286 | +31.2% | 0.578 | +5.1% | 34% | 62 (42) |
| ALL | 0.431 | +22.0% | 0.273 | +17.1% | 0.551 | +2.8% | 13% | 181 (262) |

## Changes applied by the controller

21 applied — neutral: 8, beneficial: 11, harmful: 2

- ks_cancel v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.006 → **neutral**
- nw_renewal v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.006 → **neutral**
- nw_renewal v3 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=+0.038 didΔ=+0.000 → **beneficial**
- ks_cancel v3 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=+0.022 didΔ=+0.000 → **beneficial**
- ks_cancel v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.032 → **beneficial**
- nw_renewal v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.008 → **neutral**
- nw_kyc v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'caller_id', 'schedule'] engageΔ=-0.011 didΔ=+0.015 → **harmful**
- ks_cancel v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.021 → **beneficial**
- nw_renewal v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.042 → **beneficial**
- nw_renewal v6 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.020 → **neutral**
- ks_cancel v7 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.004 → **neutral**
- nw_renewal v7 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.006 → **neutral**
- nw_renewal v8 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.080 didΔ=+0.000 → **beneficial**
- ks_cancel v8 (controller_approved) dims=['prompt_version'] engageΔ=-0.047 didΔ=+0.000 → **harmful**
- nw_renewal v9 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.169 → **beneficial**
- nw_renewal v10 (controller_approved) dims=['voice'] engageΔ=+0.030 didΔ=+0.000 → **beneficial**
- nw_kyc v4 (controller_approved) dims=['welcome_message', 'caller_id'] engageΔ=+0.032 didΔ=+0.184 → **beneficial**
- nw_kyc v5 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.008 → **neutral**
- ks_cancel v9 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.080 didΔ=+0.000 → **beneficial**
- ks_cancel v10 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nw_kyc v6 (controller_approved) dims=['voice'] engageΔ=+0.028 didΔ=+0.000 → **beneficial**

## Governance

```
{
  "approval_requests": 15,
  "decisions": {
    "approved": 12,
    "rejected": 3,
    "expired": 0
  },
  "rejection_reasons": {
    "approver declined (judgement call)": 3
  },
  "applied_via_approval": 11,
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
    "type": "supervisor_edit",
    "workflow": "ks_cancel",
    "at": "D2 14:00",
    "mttr_minutes": 1575,
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
      "4": 0.079,
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
    "2": 0.173,
    "3": 0.23,
    "4": 0.12,
    "5": 0.0,
    "6": 0.0,
    "7": 0.0,
    "8": 0.0
  },
  "ks_cancel:welcome_message=W2": {
    "2": 0.252,
    "3": 0.254,
    "4": 0.249,
    "5": 0.154,
    "6": 0.0,
    "7": 0.0,
    "8": 0.0
  }
}
```

Credits used: 4 · validation runs: 2 · LLM fix calls: 0