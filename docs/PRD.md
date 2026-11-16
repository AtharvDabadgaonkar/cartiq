# CartIQ — Product Requirements Document

> Status: **outline written in Phase 1.** Written in full in Phase 9, once the
> KPI baselines it should quote actually exist and are reproducible via
> `make metrics`.

## Problem

Commerce teams can see *that* conversion is flat. They struggle to say which
specific moment in the journey is costing them revenue, what to do about it, and
whether what they shipped actually worked. Analytics tools diagnose but do not
intervene; experimentation tools measure but do not diagnose; personalisation
vendors intervene but prove their own impact.

## Target users

| User | Job to be done |
| --- | --- |
| Shopper | Find the right product quickly and check out without friction |
| Product Manager | Decide what to build next, and defend the decision with evidence |
| Growth / Lifecycle | Recover abandoning carts without discounting reflexively |
| Merchandiser | Keep the catalog findable — increasingly, by AI shopping agents |

## Goals

1. Attribute lost revenue to specific journey steps and segments
2. Ship interventions against the largest leak, each independently flag-gated
3. Measure every intervention with correct statistics and explicit guardrails
4. Make the loop repeatable: ask a question in words, get a sourced answer

## Non-goals

- Real payment processing
- Multi-tenant or production-scale ingestion
- A recommendation system competing with a dedicated vendor on relevance
- Any claim that simulated experiment results are real-world results

## To be completed in Phase 9

MVP scope, user stories with acceptance criteria, KPI tree (primary, secondary,
guardrail) with baselines from `reports/metrics.json`, risks and mitigations,
and the Phase 2 roadmap.
