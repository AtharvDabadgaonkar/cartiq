"""Console information architecture.

Single declaration, mirrored by apps/web/app/console/sections.ts so the
storefront can link to the right console page. Each section lights up in its
own build phase.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Section:
    """One console section."""

    key: str
    label: str
    icon: str
    phase: int
    blurb: str


SECTIONS: tuple[Section, ...] = (
    Section(
        key="overview",
        label="Overview",
        icon=":material/dashboard:",
        phase=9,
        blurb=(
            "The story in one screen: the top friction point, the intervention shipped "
            "against it, the experiment result, and the next bet."
        ),
    ),
    Section(
        key="funnel",
        label="Funnel",
        icon=":material/filter_alt:",
        phase=4,
        blurb=(
            "Visit → browse → product view → add to cart → checkout → shipping → payment → "
            "purchase, with drop-off per step, sliceable by device, traffic source, new vs "
            "returning, segment and date range."
        ),
    ),
    Section(
        key="segments",
        label="Segments",
        icon=":material/group:",
        phase=4,
        blurb=(
            "RFM segments (Champions, At Risk, New…) plus k-means behavioural clusters with "
            "plain-English descriptions, each with its own size and KPI set."
        ),
    ),
    Section(
        key="abandonment",
        label="Abandonment",
        icon=":material/remove_shopping_cart:",
        phase=5,
        blurb=(
            "Revenue-weighted friction ranking, an abandonment-risk model (logistic baseline "
            "plus gradient boosting, with AUC, precision/recall and calibration) and the nudge "
            "engine it drives."
        ),
    ),
    Section(
        key="experiments",
        label="Experiments",
        icon=":material/science:",
        phase=7,
        blurb=(
            "Design, assignment, sample size, two-proportion z and Welch tests, confidence "
            "intervals, sample-ratio-mismatch checks, guardrails, and an AI readout built only "
            "from the computed statistics."
        ),
    ),
    Section(
        key="assistant_quality",
        label="Assistant Quality",
        icon=":material/verified:",
        phase=6,
        blurb=(
            "Grounding accuracy, hallucination rate and fallback rate for the shopping "
            "assistant, computed from the LLM call log against a fixed evaluation set."
        ),
    ),
    Section(
        key="catalog_readiness",
        label="Catalog Readiness",
        icon=":material/inventory_2:",
        phase=8,
        blurb=(
            "A 0–100 score per product for how findable it is to an AI shopping agent, the "
            "score distribution, the top fixes, and AI-suggested attribute values marked as "
            "suggestions."
        ),
    ),
    Section(
        key="copilot",
        label="Copilot",
        icon=":material/chat:",
        phase=8,
        blurb=(
            "Natural-language questions compiled to SQL over allow-listed read-only views, "
            "answered with the query shown alongside the chart. Writes are blocked and "
            "validated against before execution."
        ),
    ),
)

SECTIONS_BY_KEY: dict[str, Section] = {section.key: section for section in SECTIONS}
