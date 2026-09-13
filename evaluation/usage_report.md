# Usage Report — Buy or Wait? Financial Decision Agent

## Final Full-Dataset Run Summary

**Run date:** 2026-09-13  
**Dataset:** `dataset/requests.csv` — 250 requests across 275 users  
**Output:** `output.csv` — 250 rows

---

## Model Providers and Names

| Step | Provider | Model | Purpose |
|---|---|---|---|
| Financial data ingestion | — | Rule-based (deterministic) | Load and type all 8 CSVs |
| FX conversion | — | Rule-based (date-matched) | Convert foreign-currency amounts |
| Cash-flow forecasting | — | Rule-based (simulation) | Day-by-day balance projection |
| Decision policy | — | Rule-based (deterministic) | Affordability routing |
| Evidence extraction (messages/images) | — | Stub (no LLM calls made) | Optional signal extraction |

> **Note:** This submission uses a fully deterministic, rules-based pipeline with no live LLM/VLM API calls. All decisions are derived from the structured dataset files as specified in the problem statement.

---

## Model Calls

| Type | Count |
|---|---|
| LLM API calls | 0 |
| VLM API calls | 0 |
| External API calls | 0 |

---

## Token Usage

| Metric | Value |
|---|---|
| Total input tokens | 0 |
| Total output tokens | 0 |
| Total tokens | 0 |
| Average tokens per request | 0 |

---

## Cost

| Metric | Value |
|---|---|
| Estimated total cost | $0.00 |
| Estimated cost per request | $0.00 |

---

## Runtime

| Metric | Value |
|---|---|
| Total runtime | ~45 seconds |
| Average per request | ~0.18 seconds |
| Requests processed | 250 / 250 |

---

## Pipeline Architecture

```
dataset/requests.csv
        ↓
  [Ingestion] load_dataset()
    - financial_profiles.csv     → FinancialProfile (min_balance, priorities)
    - financial_events.csv       → FinancialEvent (settled/pending/scheduled)
    - exchange_rates.csv         → ExchangeRateIndex (date-matched FX)
    - request_payment_options.csv → PaymentOption (installment plans)
    - messages.csv               → Evidence (untrusted, for context)
    - images.csv                 → Evidence (untrusted, image references)
        ↓
  [UserFinancialState] per-user snapshot
    - current balance
    - recurring expenses detected by cadence
    - pending/scheduled debits reserved
        ↓
  [Forecaster] 90-day cash-flow simulation
    - Projects income (monthly cadence snapped to salary day-of-month)
    - Projects essential recurring expenses (rent, utilities, insurance,
      groceries, transport, education, healthcare, debt_repayment)
    - Reserves pending debits; excludes pending credits
        ↓
  [DecisionEngine] per-request decision
    - Checks affordable_now → full_payment
    - Checks installment options vs max_installment_months preference
    - Checks earliest_safe_date → affordable_later / wait
    - Checks spending changes (stop/reduce flexible events) → affordable_with_plan
    - Falls back to not_affordable / not_recommended
        ↓
output.csv (250 rows, validated)
```
