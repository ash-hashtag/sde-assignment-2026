# Grade report — public_03_load

## Outcomes vs baseline (no-op controller)

| workflow | conclusion rate | Δ | pickup | Δ | engagement | Δ | engagement gap captured | hallucinated calls (base) |
|---|---|---|---|---|---|---|---|---|
| arav_cancel_2 | 0.380 | +11.4% | 0.255 | +4.3% | 0.527 | +5.2% | 44% | 397 (408) |
| arav_kyc_1 | 0.498 | +40.7% | 0.278 | +29.8% | 0.612 | +2.7% | 19% | 434 (370) |
| arav_renewal_0 | 0.482 | +19.8% | 0.289 | +9.5% | 0.592 | +8.9% | 46% | 434 (440) |
| kest_cancel_2 | 0.380 | +12.1% | 0.256 | +5.0% | 0.525 | +5.3% | 34% | 438 (411) |
| kest_kyc_1 | 0.456 | +29.2% | 0.258 | +20.6% | 0.611 | +2.8% | 19% | 426 (339) |
| kest_renewal_0 | 0.476 | +19.1% | 0.287 | +8.8% | 0.584 | +7.7% | 34% | 443 (433) |
| nort_cancel_2 | 0.393 | +15.9% | 0.262 | +7.9% | 0.527 | +5.6% | 42% | 411 (393) |
| nort_kyc_1 | 0.467 | +32.0% | 0.259 | +21.4% | 0.622 | +4.5% | 24% | 433 (323) |
| nort_renewal_0 | 0.481 | +18.9% | 0.287 | +9.0% | 0.594 | +8.4% | 47% | 468 (411) |
| tide_cancel_2 | 0.398 | +17.3% | 0.262 | +7.3% | 0.533 | +6.8% | 52% | 426 (407) |
| tide_kyc_1 | 0.408 | +15.3% | 0.237 | +10.2% | 0.606 | +2.3% | 10% | 339 (356) |
| tide_renewal_0 | 0.477 | +18.9% | 0.289 | +9.2% | 0.585 | +7.9% | 41% | 425 (438) |
| ALL | 0.441 | +20.9% | 0.268 | +11.5% | 0.577 | +6.1% | 34% | 5074 (4729) |

## Changes applied by the controller

67 applied — neutral: 29, beneficial: 37, harmful: 1

- arav_cancel_2 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.006 → **neutral**
- arav_renewal_0 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.006 → **neutral**
- kest_cancel_2 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.006 → **neutral**
- kest_renewal_0 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.006 → **neutral**
- nort_cancel_2 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.006 → **neutral**
- nort_renewal_0 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.006 → **neutral**
- tide_cancel_2 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.006 → **neutral**
- tide_renewal_0 v2 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.006 → **neutral**
- kest_renewal_0 v3 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.019 → **neutral**
- kest_renewal_0 v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.035 → **beneficial**
- arav_kyc_1 v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'caller_id', 'schedule'] engageΔ=+0.037 didΔ=+0.051 → **beneficial**
- kest_renewal_0 v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.019 → **neutral**
- tide_cancel_2 v3 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=-0.003 didΔ=+0.000 → **neutral**
- arav_cancel_2 v3 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=-0.003 didΔ=+0.000 → **neutral**
- kest_cancel_2 v3 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=-0.003 didΔ=+0.000 → **neutral**
- nort_cancel_2 v3 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=-0.003 didΔ=+0.000 → **neutral**
- tide_renewal_0 v3 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=+0.051 didΔ=+0.000 → **beneficial**
- tide_renewal_0 v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.019 → **neutral**
- tide_renewal_0 v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.037 → **beneficial**
- nort_renewal_0 v3 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=+0.051 didΔ=+0.000 → **beneficial**
- nort_renewal_0 v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.019 → **neutral**
- nort_renewal_0 v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.042 → **beneficial**
- arav_renewal_0 v3 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=+0.051 didΔ=+0.000 → **beneficial**
- arav_renewal_0 v4 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=-0.019 → **neutral**
- arav_renewal_0 v5 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.046 → **beneficial**
- nort_renewal_0 v6 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.016 → **neutral**
- arav_cancel_2 v4 (controller_approved) dims=['welcome_message'] engageΔ=+0.025 didΔ=+0.000 → **beneficial**
- nort_kyc_1 v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'caller_id', 'schedule'] engageΔ=+0.037 didΔ=+0.060 → **beneficial**
- tide_cancel_2 v4 (controller_approved) dims=['welcome_message'] engageΔ=+0.025 didΔ=+0.000 → **beneficial**
- tide_renewal_0 v6 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.020 → **neutral**
- arav_renewal_0 v6 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.013 → **neutral**
- kest_kyc_1 v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'caller_id', 'schedule'] engageΔ=+0.037 didΔ=+0.062 → **beneficial**
- nort_renewal_0 v7 (controller_approved) dims=['welcome_message'] engageΔ=+0.072 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v5 (controller_approved) dims=['voice'] engageΔ=+0.007 didΔ=+0.000 → **neutral**
- nort_cancel_2 v4 (controller_approved) dims=['welcome_message'] engageΔ=+0.025 didΔ=+0.000 → **beneficial**
- arav_renewal_0 v7 (controller_approved) dims=['welcome_message'] engageΔ=+0.072 didΔ=+0.000 → **beneficial**
- arav_renewal_0 v8 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.009 → **neutral**
- tide_cancel_2 v5 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.077 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v6 (controller_approved) dims=['welcome_message'] engageΔ=+0.018 didΔ=+0.000 → **beneficial**
- nort_cancel_2 v5 (controller_approved) dims=['voice'] engageΔ=+0.058 didΔ=+0.000 → **beneficial**
- tide_kyc_1 v2 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'caller_id', 'schedule'] engageΔ=+0.037 didΔ=+0.057 → **beneficial**
- arav_kyc_1 v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.482 → **beneficial**
- kest_renewal_0 v6 (controller_approved) dims=['cohorts', 'welcome_message', 'voice', 'schedule'] engageΔ=+0.051 didΔ=+0.000 → **beneficial**
- tide_renewal_0 v7 (controller_approved) dims=['welcome_message'] engageΔ=+0.072 didΔ=+0.000 → **beneficial**
- nort_renewal_0 v8 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- nort_kyc_1 v3 (controller_approved) dims=['voice'] engageΔ=+0.040 didΔ=+0.000 → **beneficial**
- nort_cancel_2 v6 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.051 → **beneficial**
- tide_cancel_2 v6 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.052 → **beneficial**
- kest_kyc_1 v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.416 → **beneficial**
- nort_kyc_1 v4 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.417 → **beneficial**
- nort_renewal_0 v9 (controller_approved) dims=['voice'] engageΔ=-0.002 didΔ=+0.000 → **neutral**
- kest_cancel_2 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.105 didΔ=+0.000 → **beneficial**
- arav_cancel_2 v7 (controller_approved) dims=['voice'] engageΔ=+0.051 didΔ=+0.000 → **beneficial**
- kest_renewal_0 v7 (controller_approved) dims=['welcome_message'] engageΔ=+0.072 didΔ=+0.000 → **beneficial**
- arav_renewal_0 v9 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- arav_kyc_1 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.086 didΔ=+0.000 → **beneficial**
- kest_kyc_1 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.086 didΔ=+0.000 → **beneficial**
- nort_kyc_1 v5 (controller_approved) dims=['welcome_message'] engageΔ=+0.044 didΔ=+0.000 → **beneficial**
- arav_renewal_0 v10 (controller_auto) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- kest_cancel_2 v5 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.052 → **beneficial**
- arav_cancel_2 v8 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.053 → **beneficial**
- nort_kyc_1 v6 (controller_approved) dims=['welcome_message'] engageΔ=-0.061 didΔ=+0.000 → **harmful**
- tide_kyc_1 v3 (controller_approved) dims=['caller_id'] engageΔ=+0.000 didΔ=+0.568 → **beneficial**
- kest_renewal_0 v8 (controller_approved) dims=['voice'] engageΔ=-0.000 didΔ=+0.000 → **neutral**
- nort_renewal_0 v10 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**
- tide_kyc_1 v4 (controller_approved) dims=['welcome_message', 'voice'] engageΔ=+0.086 didΔ=+0.000 → **beneficial**
- nort_renewal_0 v11 (controller_approved) dims=['voice'] engageΔ=+0.000 didΔ=+0.000 → **neutral**

## Governance

```
{
  "approval_requests": 58,
  "decisions": {
    "approved": 48,
    "rejected": 10,
    "expired": 0
  },
  "rejection_reasons": {
    "approver declined (judgement call)": 10
  },
  "applied_via_approval": 45,
  "auto_applied": 22,
  "auto_apply_rejected": 0,
  "apply_conflicts": 3,
  "lapsed": 0,
  "peak_requests_per_24h": {
    "arav_cancel_2": 3,
    "arav_kyc_1": 2,
    "arav_renewal_0": 2,
    "nort_cancel_2": 3,
    "nort_kyc_1": 2,
    "nort_renewal_0": 3,
    "tide_cancel_2": 3,
    "tide_kyc_1": 2,
    "tide_renewal_0": 2,
    "kest_cancel_2": 1,
    "kest_kyc_1": 2,
    "kest_renewal_0": 1
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
    "3": 0.85,
    "4": 0.852
  },
  "arav_renewal_0:welcome_message=W3": {
    "3": 0.851,
    "4": 0.849
  },
  "tide_renewal_0:welcome_message=W3": {
    "3": 0.849,
    "4": 0.851
  },
  "kest_renewal_0:welcome_message=W3": {
    "4": 0.845
  }
}
```

Credits used: 0 · validation runs: 0 · LLM fix calls: 0