# Metrics dictionary

> Status: **skeleton written in Phase 1.** Definitions are added in the phase
> that computes them. Every chart in the console links here, and every figure
> quoted anywhere in the project is produced by `make metrics` into
> `reports/metrics.json`.

## How to read an entry

| Field | Meaning |
| --- | --- |
| **Definition** | The metric in one sentence, in business terms |
| **Formula** | Exactly how it is computed, in terms of events or models |
| **Grain** | What one row is (session, user, day, product) |
| **Provenance** | `real_dataset`, `simulated`, `mixed` or `model_eval` |
| **Source** | The SQL model, script or test that produces it |
| **Gotchas** | What it does *not* mean |

## Event contract

The authoritative event list is `packages/shared/src/events.ts`, served live at
`GET /schema` on the analytics API. Events:
`session_start`, `page_view`, `search`, `product_view`, `add_to_cart`,
`remove_from_cart`, `checkout_start`, `shipping_step`, `payment_step`,
`purchase`, `assistant_open`, `assistant_query`, `assistant_click`,
`recommendation_impression`, `recommendation_click`, `nudge_shown`,
`nudge_clicked`.

Canonical funnel: visit → search/browse → product view → add to cart →
checkout → shipping → payment → purchase.

## Entries by phase

| Metric | Phase |
| --- | --- |
| Conversion rate, AOV, revenue per visitor, cart abandonment rate, search-to-purchase rate, CLV | 4 |
| Funnel step drop-off, revenue-weighted friction rank | 4 |
| RFM segments and k-means cluster definitions | 4 |
| Abandonment-risk model: AUC, precision/recall, calibration | 5 |
| Assistant grounding accuracy, hallucination rate, fallback rate | 6 |
| Experiment statistics: lift, CI, p-value, SRM check, guardrails | 7 |
| Catalog readiness score (0–100) and its component weights | 8 |
