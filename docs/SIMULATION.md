# Simulated sessions — assumptions and parameters

> Status: **placeholder written in Phase 1.** The simulator itself lands in
> Phase 2 (`scripts/simulate.py`), and this file is filled in alongside it,
> before any simulated number appears anywhere in the project.

## Why there is a simulator at all

Diagnosis (Modules 1–3) runs on a **real** public e-commerce behaviour dataset.
That dataset contains no experiment: there is no treatment group, because
nobody ever shipped the AI assistant or the recovery nudges to those shoppers.

To demonstrate an experiment honestly, CartIQ generates shopper sessions with
explicit, configurable behavioural parameters — including the treatment effect
of each intervention — and then recovers that effect using the same statistics
a real readout would use.

## The two rules this file exists to enforce

1. **Every simulated number is labelled `simulated`** — in the console, in the
   README, in `reports/metrics.json` and in `docs/EXPERIMENT_READOUT.md`. A
   simulated lift is never described as a real-world result.
2. **The effect is a documented input, not a hard-coded output.** The simulator
   is told "the assistant raises add-to-cart probability by X for segment Y".
   The Experiment Studio does not know X. It must estimate it from the generated
   sessions through correct statistics, and the test suite asserts that the
   recovered confidence interval contains the configured X — and that an A/A
   configuration produces no significant effect at roughly the nominal
   false-positive rate.

## Parameters (to be filled in Phase 2)

Each of the following will be listed with its value, its unit, and one sentence
of plain-language justification:

- Funnel step transition probabilities, by segment and device
- Session arrival volume and its distribution over the day/week
- Price sensitivity and shipping-cost sensitivity
- Cart size distribution and item price distribution
- Return/refund probability (guardrail metric)
- Treatment effect per intervention: AI assistant, personalisation, each nudge
- Noise: within-user variance and day-of-week seasonality
- Random seed (`SIM_SEED`, default 42) — every run is reproducible

## Reproducibility

Every run writes a `simulation_runs` row holding the seed, the complete
parameter set and the git SHA, and every generated event references it. Any
simulated figure can therefore be traced to the exact run and parameters that
produced it, and regenerated with one command.
