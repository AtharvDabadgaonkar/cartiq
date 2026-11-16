# Experiment readout

> Status: **placeholder.** This file is **generated from an actual run** in
> Phase 7 (`make simulate` → Experiment Studio → readout). It is deliberately
> empty until then: writing a plausible-looking readout before running the
> experiment is exactly the thing this project is built to argue against.

The generated readout will contain:

1. **Hypothesis** — what was expected to change, for whom, and why
2. **Design** — variants, traffic split, unit of randomisation, exposure,
   primary metric, guardrail metrics, minimum detectable effect, required sample
   size and the baseline it was computed from
3. **Validity checks** — sample ratio mismatch (chi-square), assignment
   balance, exposure consistency across the rollout ramp
4. **Results** — per metric: absolute and relative lift, confidence interval,
   p-value, and the test used (two-proportion z for proportions, Welch's t for
   means), optionally with CUPED variance reduction
5. **Guardrails** — return rate, page latency, assistant hallucination rate,
   nudge dismissal rate, each against its threshold
6. **Decision** — ship / don't ship / iterate, with the reasoning, generated
   only from the computed statistics
7. **Provenance** — the simulation run id, seed and parameter set, and a clear
   statement that the sessions are **simulated**
