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

## Phase 4 entries — funnel, KPIs, segments

All funnel and session-denominated figures are **simulated**; value and
segmentation figures are **real**. The split is not a preference, it is forced:
see "Why the funnel is simulated" above.

### Funnel

| Metric | Definition | Grain | Provenance |
| --- | --- | --- | --- |
| Step sessions | Distinct sessions that emitted any event for a step | session | simulated |
| `step_rate` | Sessions at a step ÷ sessions at the previous step | step | simulated |
| `overall_rate` | Sessions at a step ÷ sessions at step 0 | step | simulated |
| `drop_rate` | Sessions lost entering a step ÷ sessions at the previous step | step | simulated |

A step is "reached" if the session emitted *any* event for it; `max_step_depth`
is derived from the deepest step actually reached, so an out-of-order log
cannot inflate the funnel.

### KPI tiles

| Metric | Formula | Needs sessions? |
| --- | --- | --- |
| Conversion rate | converting sessions ÷ all sessions | **yes** |
| Average order value | revenue ÷ orders | no |
| Revenue per visitor | revenue ÷ all sessions | **yes** |
| Cart abandonment rate | sessions that carted but never bought ÷ sessions that carted | **yes** |
| Search-to-purchase rate | sessions that searched *and* bought ÷ sessions that searched | **yes** |
| Customer lifetime value | mean observed revenue per attributed customer | no |

**"Needs sessions" is load-bearing.** A transactional import contains only
completed orders, so every session in it converted by construction. CartIQ
refuses to compute those metrics there and says why, rather than rendering a
100% conversion rate that would look entirely plausible.

### Revenue rule

Revenue is **source-aware**, because the sources are different grains:

| Source | Shape | Revenue |
| --- | --- | --- |
| `REAL_DATASET` | one purchase event per invoice line, unit price | `SUM(price × quantity)` |
| `SIMULATED`, `LIVE_DEMO` | one purchase event per order, order total | `SUM(price)` |

Applying one rule to both would multiply simulated revenue by the basket size.

### Friction ranking

`revenue_at_risk = dropped × P(convert | reached step) × revenue per conversion`

An **upper bound on recoverable revenue, not a forecast**: it assumes a
recovered session behaves like one that already got through. Ranked descending;
`share_of_loss` sums to 1.

### RFM segments

Recency, frequency and monetary value, each scored into quintiles *within a
source*, then combined by a readable rule ladder (not a 125-cell lookup).
Recency is measured against **the last date in the data**, not the wall clock —
the dataset ends in 2011, so a wall-clock recency would mark every customer
lapsed.

| Segment | Means | Why it matters |
| --- | --- | --- |
| Champions | Recent, frequent, highest spend | Most exposed to a pricing or delivery change |
| Loyal | Regular, above-average spend | Basket growth, not acquisition |
| Potential loyalist | Recent, a few orders | Where loyalty is actually won |
| New customers | Very recent, one order | Second experience decides retention |
| At risk | Were frequent and valuable, now quiet | Highest recoverable revenue |
| Can't lose them | Biggest spenders, gone quiet | Human outreach, not a discount |
| Hibernating | Low value, long gone | Cheap reactivation only |
| Lost | Lowest on all three | Suppress from paid targeting |

Only **attributed** customers are scored. The import keeps unattributed lines
so revenue reconciles, but they cannot be assigned to a person, so they are
excluded here rather than silently bucketed.

### Behavioural clusters

K-means (k configurable, default 4) over recency, frequency, monetary, average
order value and tenure, **standardised first** — without that, spend alone would
decide the clusters. Descriptions are derived from where each cluster sits
against the population, so a label cannot drift away from the data.

## Phase 5 entries — abandonment risk and nudges

### Abandonment risk model

| Metric | Definition | Provenance |
| --- | --- | --- |
| `abandonment_model_rows` | Carting sessions trained and evaluated on | model_eval |
| `abandonment_model_roc_auc` | ROC AUC on a held-out split (0.5 = coin flip) | model_eval |
| `abandonment_model_average_precision` | Average precision of the selected model | model_eval |
| `abandonment_model_baseline_average_precision` | Average precision of always predicting the majority class | model_eval |
| `abandonment_model_brier_score` | Mean squared error of the predicted probability; lower is better | model_eval |
| `abandonment_model_selected` | Model chosen by Brier score | model_eval |

**Why selection is on Brier score but the headline is average precision.**
These answer different questions. Average precision is the clearest *summary*
of how well the model separates carts, so it leads the report. Brier score
decides which model *ships*, because the nudge thresholds on a probability and
Brier is a proper scoring rule — it penalises a confident wrong answer, so it
rewards calibration and ranking together. Selecting on average precision alone
once preferred the boosted model by 0.008 AP on one split while that model was
worse on AUC and 1pp worse on Brier, putting a 7pp kink in the reliability
curve exactly at the nudge threshold.

**Why average precision is the headline, not AUC.** Roughly 80% of carts are
abandoned, so a model that always answers "abandoned" already scores 0.80
average precision, 1.00 recall and 0.89 F1. Quoting precision or F1 without
that baseline beside it would be meaningless. The baseline is reported as a row
in the same table.

**Why calibration is tracked at all.** The nudge engine fires on a *threshold*
of predicted risk, so the probability has to mean what it says. A model can
rank well (good AUC) and still be badly calibrated, which would nudge the wrong
carts. The reliability curve reports predicted vs observed per probability bin
*with the bin counts*, because a bin holding twelve carts should not be read
like one holding four thousand. A test fails the build if any well-populated
bin is off by more than 5 percentage points.

**Leakage.** Features come from `mart_cart_sessions`, which excludes every
funnel step after the cart is created. A model that knows the shopper reached
the payment step scores beautifully and cannot be deployed, because by then the
decision is already made.

### Nudge engine

Rules, not a model: the model produces a calibrated score, the rules decide
what — if anything — to say.

| Order | Nudge | Flag | Fires when |
| --- | --- | --- | --- |
| 0 | *(none)* | — | risk < 75% |
| 1 | `free_shipping_threshold` | `nudge_free_shipping` | risk ≥ 75%, shipping charged, within £15 of the threshold |
| 2 | `saved_cart_reminder` | `nudge_saved_cart` | risk ≥ 85% |
| 3 | `low_stock_note` | `nudge_low_stock` | risk ≥ 75% and more than one item |

**At most one nudge per cart.** Stacking messages on a hesitant shopper turns a
helpful nudge into a dark pattern, and it would make the Phase 7 experiment
uninterpretable — you could not say which message moved anyone.

**The 75% threshold is not the classifier's 0.5.** At an ~80% base rate, 0.5
fires on virtually every cart and the nudge stops meaning anything.

Thresholds live in `packages/shared/src/nudges.ts` and
`apps/api/src/cartiq_api/nudges.py`; a parity test fails the build if they
drift, because the storefront decides in TypeScript and the console explains
the same ladder in Python.

### Guardrail signals

`nudge_shown` and `nudge_clicked` (with `action: dismiss`) are emitted by the
storefront. Dismissal rate is a Phase 7 guardrail: a nudge people close is
costing goodwill whatever it does to conversion.

## Entries by phase

| Metric | Phase |
| --- | --- |
| Conversion rate, AOV, revenue per visitor, cart abandonment rate, search-to-purchase rate, CLV | 4 ✅ |
| Funnel step drop-off, revenue-weighted friction rank | 4 ✅ |
| RFM segments and k-means cluster definitions | 4 ✅ |
| Catalog field coverage (brand, GTIN, image, category) | 2 ✅ |
| Abandonment-risk model: AUC, precision/recall, calibration | 5 ✅ |
| Assistant grounding accuracy, hallucination rate, fallback rate | 6 |
| Experiment statistics: lift, CI, p-value, SRM check, guardrails | 7 |
| Catalog readiness score (0–100) and its component weights | 8 |
