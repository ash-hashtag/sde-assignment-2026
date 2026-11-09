# Grade report — public_02_incidents

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.264 | +6.5% | 0.184 | -0.1% | 0.507 | +6.4% | 46% | 56 (330) |
| nw_kyc | 0.382 | +2.1% | 0.244 | +1.0% | 0.600 | +1.3% | -12% | 32 (31) |
| nw_renewal | 0.437 | +2.5% | 0.266 | +1.4% | 0.553 | +0.9% | 10% | 44 (55) |
| ALL | 0.347 | +3.8% | 0.224 | +0.8% | 0.545 | +2.9% | 26% | 132 (416) |

## Changes applied by the controller

10 applied — beneficial: 8, neutral: 2

- ks_cancel v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=+0.017 didΔ=+0.000 → **beneficial**
- nw_kyc v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=-0.010 didΔ=+0.000 → **neutral**
- nw_renewal v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=+0.032 didΔ=+0.000 → **beneficial**
- nw_renewal v3 (controller_approved) dims=['welcome_message'] engageΔ=+0.093 didΔ=+0.000 → **beneficial**
- ks_cancel v3 (controller_approved) dims=['voice'] engageΔ=+0.002 didΔ=+0.000 → **neutral**
- nw_renewal v4 (controller_approved) dims=['voice'] engageΔ=+0.019 didΔ=+0.000 → **beneficial**
- ks_cancel v5 (controller_approved) dims=['prompt_version'] engageΔ=+0.102 didΔ=+0.000 → **beneficial**
- ks_cancel v6 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.029 didΔ=+0.000 → **beneficial**
- nw_renewal v5 (controller_approved) dims=['voice'] engageΔ=+0.011 didΔ=+0.000 → **beneficial**
- nw_renewal v7 (controller_approved) dims=['welcome_message'] engageΔ=+0.087 didΔ=+0.000 → **beneficial**

## Governance

```
{
  "approval_requests": 11,
  "decisions": {
    "approved": 10,
    "rejected": 1,
    "expired": 0
  },
  "rejection_reasons": {
    "approver declined (judgement call)": 1
  },
  "applied_via_approval": 10,
  "auto_applied": 0,
  "auto_apply_rejected": 0,
  "apply_conflicts": 0,
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
    "type": "did_flagged",
    "workflow": "ks_cancel",
    "at": "D2 10:00",
    "flagged_did_share_by_day": {
      "2": 0.501,
      "3": 0.496,
      "4": 0.5,
      "5": 0.494,
      "6": 0.497,
      "7": 0.496,
      "8": 0.503,
      "9": 0.496
    }
  },
  {
    "type": "supervisor_edit",
    "workflow": "ks_cancel",
    "at": "D3 11:30",
    "mttr_minutes": 75,
    "fixed_by": "controller_approved"
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
    "2": 0.816,
    "3": 0.803,
    "4": 0.802,
    "5": 0.797,
    "6": 0.518,
    "7": 0.0,
    "8": 0.0,
    "9": 0.0
  }
}
```

Credits used: 4 · validation runs: 2 · LLM fix calls: 0