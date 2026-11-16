/**
 * Console information architecture.
 *
 * Mirrored by apps/console/cartiq_console/sections.py, which is the console's
 * own declaration; a parity test fails the build if the two drift. Keys here
 * are the Streamlit URL paths.
 */
export const CONSOLE_SECTIONS = {
  funnel: {
    label: 'Funnel',
    phase: 4,
    blurb:
      'Visit → browse → product view → add to cart → checkout → shipping → payment → purchase, with drop-off per step, sliceable by device, source, new vs returning, segment and date range.',
  },
  segments: {
    label: 'Segments',
    phase: 4,
    blurb:
      'RFM segments (Champions, At Risk, New…) plus k-means behavioural clusters with plain-English descriptions, each with its own size and KPI set.',
  },
  abandonment: {
    label: 'Abandonment',
    phase: 5,
    blurb:
      'Revenue-weighted friction ranking, an abandonment-risk model (logistic baseline + gradient boosting, with AUC/PR/calibration) and the nudge engine it drives.',
  },
  experiments: {
    label: 'Experiments',
    phase: 7,
    blurb:
      'Design, assignment, sample size, two-proportion z / Welch tests, confidence intervals, sample-ratio-mismatch checks, guardrails and an AI readout built only from the computed statistics.',
  },
  'assistant-quality': {
    label: 'Assistant Quality',
    phase: 6,
    blurb:
      'Grounding accuracy, hallucination rate and fallback rate for the shopping assistant, computed from the LLM call log against a fixed evaluation set.',
  },
  'catalog-readiness': {
    label: 'Catalog Readiness',
    phase: 8,
    blurb:
      'A 0–100 score per product for how findable it is to an AI shopping agent, the score distribution, the top fixes, and AI-suggested attribute values marked as suggestions.',
  },
  copilot: {
    label: 'Copilot',
    phase: 8,
    blurb:
      'Natural-language questions compiled to SQL over allow-listed read-only views, answered with the query shown alongside the chart. Writes are blocked and validated against before execution.',
  },
} as const;

export type ConsoleSectionKey = keyof typeof CONSOLE_SECTIONS;

export function isConsoleSection(value: string): value is ConsoleSectionKey {
  return Object.hasOwn(CONSOLE_SECTIONS, value);
}

/** Base URL of the Streamlit console. Set NEXT_PUBLIC_CONSOLE_URL in production. */
export function consoleUrl(): string {
  return process.env.NEXT_PUBLIC_CONSOLE_URL ?? 'http://localhost:8501';
}
