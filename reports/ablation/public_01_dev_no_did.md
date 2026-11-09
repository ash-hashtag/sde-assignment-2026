# Grade report — public_01_dev

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| ks_cancel | 0.360 | +8.2% | 0.244 | +2.3% | 0.511 | +4.0% | 32% | 44 (47) |
| nw_kyc | 0.383 | +5.2% | 0.243 | +0.2% | 0.616 | +4.3% | 22% | 28 (21) |
| nw_renewal | 0.429 | +2.2% | 0.267 | +1.4% | 0.550 | +0.8% | 11% | 52 (42) |
| ALL | 0.388 | +5.3% | 0.252 | +1.6% | 0.545 | +2.8% | 22% | 124 (110) |

## Changes applied by the controller

10 applied — neutral: 4, beneficial: 6

- ks_cancel v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=-0.003 didΔ=+0.000 → **neutral**
- nw_renewal v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=+0.051 didΔ=+0.000 → **beneficial**
- nw_kyc v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=+0.037 didΔ=+0.000 → **beneficial**
- ks_cancel v3 (controller_approved) dims=['welcome_message'] engageΔ=+0.025 didΔ=+0.000 → **beneficial**
- nw_renewal v3 (controller_approved) dims=['welcome_message'] engageΔ=+0.065 didΔ=+0.000 → **beneficial**
- ks_cancel v4 (controller_approved) dims=['voice'] engageΔ=+0.007 didΔ=+0.000 → **neutral**
- ks_cancel v5 (controller_approved) dims=['voice'] engageΔ=+0.047 didΔ=+0.000 → **beneficial**
- nw_renewal v4 (controller_approved) dims=['voice'] engageΔ=-0.001 didΔ=+0.000 → **neutral**
- nw_kyc v3 (controller_approved) dims=['welcome_message'] engageΔ=+0.042 didΔ=+0.000 → **beneficial**
- nw_renewal v5 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**

## Governance

```
{
  "approval_requests": 10,
  "decisions": {
    "approved": 10,
    "expired": 0
  },
  "rejection_reasons": {},
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
[]
```

## Decaying variants — share of in-population calls still on the variant, by day after onset

```
{
  "nw_renewal:welcome_message=W3": {
    "3": 0.793,
    "4": 0.798,
    "5": 0.804,
    "6": 0.803,
    "7": 0.796
  }
}
```

Credits used: 0 · validation runs: 0 · LLM fix calls: 0