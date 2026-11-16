# Simulated sessions — assumptions and parameters

> **Everything on this page is an input, not a finding.** These are the
> behavioural assumptions CartIQ's session simulator is given. Any number
> derived from simulated sessions is labelled **Simulated** in the console, the
> README, `reports/metrics.json` and the experiment readout. A simulated lift is
> not a real-world result and is never presented as one.

Source of truth for the values below: `apps/api/src/cartiq_api/simulation/params.py`.
A test (`test_simulation_docs.py`) fails the build if a parameter exists in code
but is not documented here.

## 1. Why a simulator exists at all

Diagnosis (Modules 1–3) runs on a **real** public dataset: UCI *Online Retail II*,
1.07M real transactions. That dataset contains no experiment. Nobody ever shipped
an AI shopping assistant or a cart-recovery nudge to those shoppers, so there is
no treatment group and no lift to measure. There is also no browsing: it records
purchases, so the journey funnel above `purchase` is not observable in it at all.

Two honest options exist: claim a lift that was never observed, or generate
sessions from assumptions stated out loud and then recover the effect with the
same statistics a real readout would use. CartIQ does the second.

## 2. The two rules this file enforces

**1. Every simulated number is labelled.** Provenance is a database column
(`events.source` = `REAL_DATASET | SIMULATED | LIVE_DEMO`), not a convention, and
every surface reports which sources its numbers cover.

**2. The effect is an input, never a hard-coded output.** The simulator is told
"the assistant multiplies product-view→add-to-cart by 1.025". The Experiment
Studio is never told that. It has to estimate the lift from the generated events
through a two-proportion z-test, and the test suite asserts that

- the recovered 95% confidence interval contains the configured effect, and
- an A/A configuration (every effect set to 1.0) produces significant results at
  roughly the nominal 5% false-positive rate, not more.

The parameters are *public* — they are on this page and on every
`simulation_runs` row. They are simply not an input to the estimator.

## 3. Reproducibility

Every run writes a `simulation_runs` row holding the seed, the complete parameter
set, the ground truth and the git SHA; every generated event references it via
`simulation_run_id`. Re-running with the same seed and size reproduces the run
exactly, and re-loading replaces its own rows rather than duplicating them.

```bash
make simulate                                  # defaults below
python scripts/simulate.py --seed 7 --aa-test  # A/A control run
python scripts/simulate.py --sessions 120000   # smaller, for a free-tier deploy
```

## 4. Population

| Parameter | Value | Why |
| --- | --- | --- |
| `seed` | 42 | Fixed so every run is reproducible. |
| `sessions` | 500,000 | Sized so the flagship experiment can actually detect its own effect: ~159k sessions per variant are needed for 80% power on a ~1.6% realised baseline, so 500k gives ~94% power. A smaller run is *underpowered by construction* and will mostly produce non-significant readouts. |
| `users` | 120,000 | Fewer users than sessions, so returning visitors genuinely repeat and RFM/CLV have repeat behaviour to work with. |
| `start_date` / `days` | 2026-01-05, 56 | Eight whole weeks starting on a Monday, so weekday seasonality is balanced. |
| `device_mix` | mobile 62%, desktop 31%, tablet 7% | Typical retail split; mobile-majority traffic is what makes mobile checkout friction the headline finding. |
| `traffic_mix` | organic 31%, paid search 22%, direct 18%, email 13%, social 11%, referral 5% | A plausible mid-size retailer mix with no single dominant channel. |
| `segment_mix` | new 46%, returning browser 30%, loyal 16%, bargain hunter 8% | Roughly half first-time traffic, a small high-value core. |

## 5. Baseline funnel

`base_transition_rates` is the probability a baseline session advances one step.
Their product is the baseline conversion rate, **2.43%**, before any device,
segment or traffic modifier. After modifiers the realised rate is ~1.6%, inside
the usual 1–3% retail band.

| Transition | Rate | Why |
| --- | --- | --- |
| visit → browse | 0.78 | Most arrivals look at something; ~22% bounce immediately. |
| browse → product view | 0.54 | About half of browsing sessions open a product. |
| product view → add to cart | 0.21 | The classic one-in-five product-page conversion. |
| add to cart → checkout | 0.52 | Roughly half of carts are abandoned before checkout starts — the single largest leak, and the one the nudges target. |
| checkout → shipping | 0.81 | Most people who start checkout reach the shipping step. |
| shipping → payment | 0.74 | Shipping cost and delivery options are where hesitation shows up. |
| payment → purchase | 0.88 | Late failures are mostly payment declines and second thoughts. |

### Modifiers

Multipliers applied to specific transitions, by device, segment and channel.

- **`device_multipliers`** — mobile is penalised where money is involved
  (cart→checkout ×0.88, checkout→shipping ×0.84, shipping→payment ×0.80,
  payment→purchase ×0.93) and not penalised while browsing. This encodes the
  most common real pattern in commerce: mobile gets the traffic, desktop gets
  the orders. Tablet is mildly penalised at shipping→payment (×0.94); desktop
  is the unmodified reference.
- **`segment_multipliers`** — `loyal` shoppers browse, add and check out more
  readily (×1.18 / ×1.35 / ×1.22). `new_visitor` adds to cart and checks out
  less (×0.82 / ×0.88). `bargain_hunter` adds to cart readily (×1.15) but
  abandons at checkout (×0.74) — a price-sensitive browser, not a buyer.
  `returning_browser` is the unmodified reference.
- **`traffic_multipliers`** — `email` traffic is pre-qualified (add-to-cart
  ×1.20, checkout ×1.10); `social` is top-of-funnel and converts poorly
  (product view ×0.88, add to cart ×0.80); `direct` completes checkout slightly
  more often (×1.08); `paid_search` adds to cart slightly more (×1.05).

## 6. Basket economics

| Parameter | Value | Why |
| --- | --- | --- |
| `cart_items_lambda` | 1.6 | Items per cart ~ 1 + Poisson(1.6), giving a mean basket of ~2.6 items. |
| `free_shipping_threshold` | £40.00 | The threshold the free-shipping nudge references. |
| `shipping_cost` | £4.95 | Charged below the threshold. |
| `shipping_cost_penalty` | 0.82 | Carts that will be charged shipping complete checkout 18% less often. Unexpected shipping cost is consistently the most-cited reason for cart abandonment. |
| `price_sensitivity` | 0.94 | Each doubling of basket value above £25 multiplies checkout completion by 0.94: bigger baskets hesitate more. |
| `base_return_rate` | 0.071 | 7.1% of orders are later returned. This is the guardrail metric, not a conversion input. |

When the catalog is available, simulated carts hold **real products at real
prices**, sampled by real purchase popularity, so basket values are grounded in
the actual dataset rather than invented.

## 7. Seasonality

- **`weekday_weights`** — Mon–Sun `(1.08, 1.05, 1.02, 1.0, 0.98, 0.82, 0.86)`.
  Weekday-heavy, as retail traffic generally is.
- **`hour_weights`** — 24 values peaking at 19:00–20:00 (1.44 / 1.36) with a
  trough at 03:00–04:00 (0.09 / 0.10), plus a lunchtime bump.

Seasonality affects *when* sessions happen, never whether they convert, so it
cannot leak into the experiment result.

## 8. Interventions and their configured effects

The `interventions` parameter holds one entry per shippable change. Each is
gated by its own feature flag and multiplies specific transitions. These are the
numbers the Experiment Studio must recover without being told them.

### `ai_shopping_assistant`
Catalog-grounded chat assistant: helps shoppers find a matching product and
compare options.

| Transition | Multiplier |
| --- | --- |
| browse → product view | **×1.015** |
| product view → add to cart | **×1.025** |

### `cart_recovery_nudges`
Risk-triggered cart nudges: distance to the free-shipping threshold, saved-cart
reminder, low-stock note.

| Transition / metric | Multiplier |
| --- | --- |
| add to cart → checkout | **×1.025** |
| shipping → payment | **×1.012** |
| return rate (guardrail) | **×1.06** |

The nudge deliberately carries a *bad* side effect: pushing hesitant shoppers
over the line also lifts returns by 6%. A readout that reports the conversion
win without catching the returns cost is doing half the job, and the guardrail
exists to catch exactly that.

### `personalised_recommendations`
Item-to-item co-occurrence recommendations with a popular-items fallback.

| Transition | Multiplier |
| --- | --- |
| browse → product view | **×1.02** |

Not part of the flagship experiment; it ships on its own flag in a later phase.

### Why the effects are this small

Compounded, the assistant and the nudges give a **7.92% relative lift** on
conversion (1.015 × 1.025 × 1.025 × 1.012). That is deliberately modest. A 20–30%
lift would make the experiment significant on any sample size and would
demonstrate nothing about the statistics; a realistic single-digit effect is what
forces correct power analysis, an honest confidence interval, and a readout that
can say "significant, but the interval is wide".

## 9. Experiments

| Parameter | Value |
| --- | --- |
| `experiments[0].key` | `flagship_assistant_nudges` |
| variants | `control` 50% / `treatment` 50% |
| `treatment` enables | `ai_shopping_assistant`, `cart_recovery_nudges` |
| `exposure` | 1.0 (all traffic eligible) |
| `assignment_salt` | `cartiq-v1`, matching `FLAG_HASH_SALT` on the web side |

Assignment uses the same FNV-1a bucketing function as the storefront, pinned to
shared cross-language test vectors, so a simulated assignment and a live one are
computed identically.

## 10. Ground truth

Each run reports both:

- **`expected_*`** — the exact population parameters, computed analytically as
  the mean over generated sessions of each session's end-to-end conversion
  probability under control and under treatment. No Monte Carlo noise, so a test
  can assert interval coverage against a known constant. `expected_relative_lift`
  is **0.0792**.
- **`realised_*`** — what this particular run produced, which is what an analyst
  would actually see and what the readout reports.

The two differ by sampling error, and that gap is the point: at the default size
the realised lift varies by several percentage points run to run even though the
truth is fixed. The readout has to be honest about that uncertainty.

## 11. What the simulator deliberately does *not* model

Stated so nobody mistakes its silence for a finding:

- No cross-session memory beyond user identity: a shopper's second session is not
  influenced by the first.
- No seasonality in *conversion*, only in traffic volume.
- No competitive, inventory or pricing dynamics.
- No novelty or decay in intervention effects; the lift is constant over time.
- No network effects between shoppers.
- Returns are drawn independently per order, not predicted from basket contents.

Each of these is a real effect in real commerce. A result produced here would not
transfer to a real storefront, which is why nothing on a simulated surface is
presented as one.
