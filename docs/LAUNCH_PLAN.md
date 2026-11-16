# Launch plan

> Status: **skeleton written in Phase 1**, completed in Phase 9 once the
> interventions and their guardrails exist.

## Rollout stages

Each intervention (AI shopping assistant, personalisation module, each recovery
nudge) is behind its own feature flag and ramps independently:

| Stage | Traffic | Minimum dwell | Go criteria | Rollback trigger |
| --- | --- | --- | --- | --- |
| 1 | 1% | 24h | No error-rate or latency regression | any guardrail breach |
| 2 | 10% | 72h | Primary metric directionally positive, guardrails flat | TBD Phase 9 |
| 3 | 50% | 1 week | Primary metric significant at the planned α | TBD Phase 9 |
| 4 | 100% | — | Readout says ship | TBD Phase 9 |

Exposure ramping uses a separate hash namespace from variant assignment, so
moving from 1% to 10% never reassigns an already-exposed user.

## To be completed in Phase 9

- Concrete go/no-go thresholds per guardrail metric
- Monitoring: which dashboard, which alert, who is on the hook
- Kill-switch procedure and expected time to full rollback
- Communication plan (who hears about a rollback, and how fast)
