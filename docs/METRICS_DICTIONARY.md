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

## Data provenance

Every metric carries one of these labels, and the two are never mixed in one
number without saying so.

| Provenance | Source | What it can support |
| --- | --- | --- |
| `real_dataset` | UCI Online Retail II (CC BY 4.0), loaded by `scripts/ingest.py` | Revenue, AOV, basket size, RFM, CLV, returns, catalog coverage |
| `simulated` | `scripts/simulate.py`, parameters in [SIMULATION.md](SIMULATION.md) | Journey funnel, drop-off, experiment lifts, guardrails |
| `mixed` | Both, each series labelled individually | Side-by-side comparisons only |
| `model_eval` | A model's own held-out evaluation | AUC, precision/recall, calibration, hallucination rate |

### Why the funnel is simulated

The real dataset records purchases, not browsing, so only `visit` and `purchase`
are observable in it. Each import declares its `observable_steps`, and the
console marks every step it cannot measure from real rows. The steps between are
measured on simulated sessions and labelled **Simulated** wherever they appear.

### Fields a source cannot observe

Recorded as `unknown` (`device`, `traffic_source`) or `NULL` (`page`,
`is_new_user`, `user_id`, `brand`, `gtin`, `image_url`). Never imputed. A metric
that would need an unobservable field is not reported for that source.

## Phase 2 entries

| Metric | Definition | Grain | Provenance |
| --- | --- | --- | --- |
| `real_events` | Event rows imported from the real dataset | event | real_dataset |
| `real_purchase_lines` | Purchase events, one per invoice line | event | real_dataset |
| `real_orders` | Distinct invoices; one invoice is treated as one session | order | real_dataset |
| `real_customers` | Distinct attributed customers who purchased | customer | real_dataset |
| `real_anonymous_line_share` | Share of purchase lines with no customer id. Kept so revenue reconciles; excluded from RFM | line | real_dataset |
| `real_gross_revenue` | `SUM(price * quantity)` over real purchase lines, before returns | — | real_dataset |
| `real_return_lines` | Cancellation lines, for the return-rate guardrail | line | real_dataset |
| `catalog_products` | Products derived from the real dataset | product | real_dataset |
| `catalog_categorised_share` | Share matched by a category rule; the rest stay `uncategorised` | product | real_dataset |
| `catalog_brand_coverage` | Share with a brand. 0 by construction: the source carries none | product | real_dataset |
| `catalog_gtin_coverage` | Share with a GTIN | product | real_dataset |
| `catalog_image_coverage` | Share with an image | product | real_dataset |
| `simulated_events` | Event rows from the session simulator | event | simulated |
| `simulated_sessions` | Sessions generated | session | simulated |
| `simulated_configured_relative_lift` | The lift the simulator was *configured* to produce. The Experiment Studio never reads it | — | simulated |

## Entries by phase

| Metric | Phase |
| --- | --- |
| Conversion rate, AOV, revenue per visitor, cart abandonment rate, search-to-purchase rate, CLV | 4 |
| Funnel step drop-off, revenue-weighted friction rank | 4 |
| RFM segments and k-means cluster definitions | 4 |
| Catalog field coverage (brand, GTIN, image, category) | 2 ✅ |
| Abandonment-risk model: AUC, precision/recall, calibration | 5 |
| Assistant grounding accuracy, hallucination rate, fallback rate | 6 |
| Experiment statistics: lift, CI, p-value, SRM check, guardrails | 7 |
| Catalog readiness score (0–100) and its component weights | 8 |
