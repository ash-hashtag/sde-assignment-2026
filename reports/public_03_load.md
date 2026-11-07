# Grade report — public_03_load

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| arav_cancel_2 | 0.400 | +17.1% | 0.266 | +8.9% | 0.530 | +5.8% | 46% | 489 (408) |
| arav_kyc_1 | 0.466 | +31.6% | 0.260 | +21.3% | 0.618 | +3.8% | 25% | 452 (370) |
| arav_renewal_0 | 0.472 | +17.4% | 0.287 | +8.8% | 0.581 | +6.9% | 36% | 476 (440) |
| kest_cancel_2 | 0.402 | +18.7% | 0.266 | +9.5% | 0.532 | +6.7% | 44% | 466 (411) |
| kest_kyc_1 | 0.437 | +23.9% | 0.245 | +14.7% | 0.620 | +4.4% | 26% | 376 (339) |
| kest_renewal_0 | 0.473 | +18.4% | 0.287 | +8.9% | 0.579 | +6.7% | 33% | 479 (433) |
| nort_cancel_2 | 0.394 | +16.3% | 0.263 | +8.6% | 0.529 | +6.1% | 40% | 394 (393) |
| nort_kyc_1 | 0.421 | +19.0% | 0.239 | +12.2% | 0.617 | +3.6% | 21% | 370 (323) |
| nort_renewal_0 | 0.476 | +17.6% | 0.287 | +9.1% | 0.585 | +6.8% | 38% | 459 (411) |
| tide_cancel_2 | 0.399 | +17.7% | 0.266 | +8.8% | 0.532 | +6.6% | 48% | 400 (407) |
| tide_kyc_1 | 0.411 | +16.4% | 0.237 | +10.4% | 0.608 | +2.7% | 15% | 359 (356) |
| tide_renewal_0 | 0.481 | +19.9% | 0.288 | +9.2% | 0.589 | +8.6% | 40% | 484 (438) |
| ALL | 0.436 | +19.5% | 0.266 | +10.7% | 0.576 | +5.9% | 34% | 5204 (4729) |

## Changes applied by the controller

64 applied — neutral: 24, beneficial: 40

- arav_cancel_2 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.006 → **neutral**
- arav_renewal_0 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.006 → **neutral**
- kest_cancel_2 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.006 → **neutral**
- kest_renewal_0 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.006 → **neutral**
- nort_cancel_2 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.006 → **neutral**
- nort_renewal_0 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.006 → **neutral**
- tide_cancel_2 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.006 → **neutral**
- tide_renewal_0 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.006 → **neutral**
- kest_renewal_0 v3 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.019 → **neutral**
- arav_kyc_1 v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'caller_id', 'schedule'] engageΔ=+0.037 didΔ=+0.051 → **beneficial**
- kest_renewal_0 v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.056 → **beneficial**
- tide_cancel_2 v3 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=-0.003 didΔ=+0.000 → **neutral**
- arav_cancel_2 v3 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=-0.003 didΔ=+0.000 → **neutral**
- kest_cancel_2 v3 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=-0.003 didΔ=+0.000 → **neutral**
- nort_cancel_2 v3 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=-0.003 didΔ=+0.000 → **neutral**
- tide_renewal_0 v3 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=+0.050 didΔ=+0.000 → **beneficial**
- tide_renewal_0 v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.019 → **neutral**
- nort_renewal_0 v3 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=+0.051 didΔ=+0.000 → **beneficial**
- nort_renewal_0 v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.019 → **neutral**
- arav_renewal_0 v3 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=+0.051 didΔ=+0.000 → **beneficial**
- arav_renewal_0 v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.019 → **neutral**
- tide_renewal_0 v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.060 → **beneficial**
- nort_renewal_0 v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.060 → **beneficial**
- arav_renewal_0 v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.061 → **beneficial**
- nort_kyc_1 v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'caller_id', 'schedule'] engageΔ=+0.038 didΔ=+0.060 → **beneficial**
- tide_cancel_2 v4 (controller_approved) dims=['welcome_message'] engageΔ=+0.025 didΔ=+0.000 → **beneficial**
- nort_cancel_2 v4 (controller_approved) dims=['welcome_message'] engageΔ=+0.025 didΔ=+0.000 → **beneficial**
- kest_cancel_2 v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.029 → **beneficial**
- nort_cancel_2 v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.029 → **beneficial**
- tide_cancel_2 v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.029 → **beneficial**
- arav_cancel_2 v4 (controller_approved) dims=['welcome_message'] engageΔ=+0.025 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.030 → **beneficial**
- kest_kyc_1 v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'caller_id', 'schedule'] engageΔ=+0.037 didΔ=+0.062 → **beneficial**
- tide_cancel_2 v6 (controller_approved) dims=['voice'] engageΔ=+0.054 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v6 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.015 → **neutral**
- kest_cancel_2 v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.015 → **neutral**
- nort_cancel_2 v6 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.015 → **neutral**
- tide_cancel_2 v7 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.017 → **neutral**
- arav_cancel_2 v7 (controller_approved) dims=['welcome_message'] engageΔ=+0.017 didΔ=+0.000 → **beneficial**
- kest_cancel_2 v6 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.081 didΔ=+0.000 → **beneficial**
- tide_renewal_0 v6 (controller_approved) dims=['welcome_message'] engageΔ=+0.065 didΔ=+0.000 → **beneficial**
- nort_cancel_2 v7 (controller_approved) dims=['voice'] engageΔ=+0.055 didΔ=+0.000 → **beneficial**
- tide_kyc_1 v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'caller_id', 'schedule'] engageΔ=+0.037 didΔ=+0.057 → **beneficial**
- nort_renewal_0 v6 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.066 didΔ=+0.000 → **beneficial**
- kest_renewal_0 v5 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=+0.051 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v8 (controller_approved) dims=['voice'] engageΔ=+0.055 didΔ=+0.000 → **beneficial**
- arav_kyc_1 v3 (controller_approved) dims=['welcome_message'] engageΔ=+0.042 didΔ=+0.000 → **beneficial**
- arav_renewal_0 v6 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.066 didΔ=+0.000 → **beneficial**
- nort_kyc_1 v3 (controller_approved) dims=['voice'] engageΔ=+0.037 didΔ=+0.000 → **beneficial**
- kest_cancel_2 v7 (controller_approved) dims=['welcome_message'] engageΔ=+0.017 didΔ=+0.000 → **beneficial**
- tide_renewal_0 v7 (controller_approved) dims=['voice'] engageΔ=-0.001 didΔ=+0.000 → **neutral**
- kest_renewal_0 v6 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.065 didΔ=+0.000 → **beneficial**
- arav_kyc_1 v4 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.495 → **beneficial**
- kest_kyc_1 v3 (controller_approved) dims=['welcome_message', 'voice', 'caller_id'] engageΔ=+0.079 didΔ=+0.130 → **beneficial**
- nort_kyc_1 v4 (controller_approved) dims=['welcome_message', 'caller_id'] engageΔ=+0.041 didΔ=+0.324 → **beneficial**
- tide_kyc_1 v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.422 → **beneficial**
- tide_cancel_2 v8 (controller_approved) dims=['welcome_message'] engageΔ=+0.016 didΔ=+0.000 → **beneficial**
- arav_renewal_0 v7 (controller_approved) dims=['voice'] engageΔ=-0.000 didΔ=+0.000 → **neutral**
- kest_kyc_1 v4 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.240 → **beneficial**
- kest_renewal_0 v7 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- tide_renewal_0 v8 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- tide_kyc_1 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.079 didΔ=+0.000 → **beneficial**
- nort_kyc_1 v5 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.021 → **beneficial**
- arav_kyc_1 v5 (controller_approved) dims=['voice'] engageΔ=+0.036 didΔ=+0.000 → **beneficial**

## Governance

```
{
  "approval_requests": 51,
  "decisions": {
    "approved": 42,
    "rejected": 8,
    "expired": 0
  },
  "rejection_reasons": {
    "approver declined (judgement call)": 8
  },
  "applied_via_approval": 40,
  "auto_applied": 24,
  "auto_apply_rejected": 0,
  "apply_conflicts": 2,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "arav_cancel_2": 2,
    "arav_kyc_1": 2,
    "arav_renewal_0": 2,
    "nort_cancel_2": 2,
    "nort_kyc_1": 1,
    "nort_renewal_0": 2,
    "tide_cancel_2": 3,
    "tide_kyc_1": 2,
    "tide_renewal_0": 2,
    "kest_cancel_2": 1,
    "kest_kyc_1": 1,
    "kest_renewal_0": 2
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
  "nort_renewal_0:welcome_message=W3": {
    "3": 0.798,
    "4": 0.8
  },
  "arav_renewal_0:welcome_message=W3": {
    "3": 0.8,
    "4": 0.806
  },
  "tide_renewal_0:welcome_message=W3": {
    "3": 0.798,
    "4": 0.8
  },
  "kest_renewal_0:welcome_message=W3": {
    "4": 0.802
  }
}
```

Credits used: 0 · validation runs: 0 · LLM fix calls: 0