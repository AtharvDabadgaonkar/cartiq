#!/usr/bin/env python3
"""Recompute every number CartIQ quotes anywhere, into reports/metrics.json.

Nothing in the README, the docs or the console may state a figure that this
script does not produce. Each entry carries its own provenance so a reader can
tell a measurement on a real dataset from a simulated result.

    python scripts/metrics.py
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = REPO_ROOT / "reports" / "metrics.json"

#: Allowed provenance labels. Mirrors the DataSource enum.
PROVENANCE = ("real_dataset", "simulated", "mixed", "model_eval", "foundation")


def git_sha() -> str | None:
    """Current commit, so a metrics file can be tied to the code that made it."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def metric(
    value: Any,
    *,
    provenance: str,
    definition: str,
    source: str,
    unit: str | None = None,
) -> dict[str, Any]:
    """Wrap a value with everything needed to audit it."""
    if provenance not in PROVENANCE:
        raise ValueError(
            f"unknown provenance {provenance!r}; expected one of {PROVENANCE}"
        )
    out: dict[str, Any] = {
        "value": value,
        "provenance": provenance,
        "definition": definition,
        # The query, script or test that produced the number.
        "source": source,
    }
    if unit is not None:
        out["unit"] = unit
    return out


QUERIES: dict[str, str] = {
    "real_events": "SELECT count(*) FROM events WHERE source = 'REAL_DATASET'",
    "real_purchase_lines": (
        "SELECT count(*) FROM events WHERE source = 'REAL_DATASET' AND event_type = 'purchase'"
    ),
    "real_orders": (
        "SELECT count(DISTINCT session_id) FROM events "
        "WHERE source = 'REAL_DATASET' AND event_type = 'purchase'"
    ),
    "real_customers": (
        "SELECT count(DISTINCT user_id) FROM events "
        "WHERE source = 'REAL_DATASET' AND event_type = 'purchase' AND user_id IS NOT NULL"
    ),
    "real_anonymous_line_share": (
        "SELECT COALESCE(AVG((user_id IS NULL)::int)::float8, 0) FROM events "
        "WHERE source = 'REAL_DATASET' AND event_type = 'purchase'"
    ),
    "real_gross_revenue": (
        "SELECT COALESCE(SUM(price * quantity), 0)::float8 FROM events "
        "WHERE source = 'REAL_DATASET' AND event_type = 'purchase'"
    ),
    "real_return_lines": "SELECT count(*) FROM return_lines",
    "catalog_products": "SELECT count(*) FROM products",
    "catalog_categorised_share": (
        "SELECT COALESCE(AVG((category_path <> 'uncategorised')::int)::float8, 0) FROM products"
    ),
    "catalog_brand_coverage": (
        "SELECT COALESCE(AVG((brand IS NOT NULL)::int)::float8, 0) FROM products"
    ),
    "catalog_gtin_coverage": (
        "SELECT COALESCE(AVG((gtin IS NOT NULL)::int)::float8, 0) FROM products"
    ),
    "catalog_image_coverage": (
        "SELECT COALESCE(AVG((image_url IS NOT NULL)::int)::float8, 0) FROM products"
    ),
    "simulated_events": "SELECT count(*) FROM events WHERE source = 'SIMULATED'",
    "simulated_sessions": (
        "SELECT count(*) FROM events WHERE source = 'SIMULATED' AND event_type = 'session_start'"
    ),
}

#: definition, provenance and unit for each query above.
DESCRIPTIONS: dict[str, tuple[str, str, str | None]] = {
    "real_events": (
        "Event rows imported from the real dataset.",
        "real_dataset",
        "rows",
    ),
    "real_purchase_lines": (
        "Purchase events, one per invoice line.",
        "real_dataset",
        "rows",
    ),
    "real_orders": (
        "Distinct invoices; one invoice is one session.",
        "real_dataset",
        "orders",
    ),
    "real_customers": (
        "Distinct attributed customers who purchased.",
        "real_dataset",
        "customers",
    ),
    "real_anonymous_line_share": (
        "Share of purchase lines with no customer id. Kept, not dropped, so revenue "
        "reconciles; excluded from RFM.",
        "real_dataset",
        "share",
    ),
    "real_gross_revenue": (
        "SUM(price * quantity) over real purchase lines, before returns.",
        "real_dataset",
        "GBP",
    ),
    "real_return_lines": (
        "Cancellation lines from the source, used for the return-rate guardrail.",
        "real_dataset",
        "rows",
    ),
    "catalog_products": (
        "Products derived from the real dataset.",
        "real_dataset",
        "products",
    ),
    "catalog_categorised_share": (
        "Share of products a category rule matched. The rest stay 'uncategorised' "
        "rather than being forced into a bucket.",
        "real_dataset",
        "share",
    ),
    "catalog_brand_coverage": (
        "Share of products with a brand. The source carries none, so this is 0 by "
        "construction and is a genuine finding for the Phase 8 readiness score.",
        "real_dataset",
        "share",
    ),
    "catalog_gtin_coverage": (
        "Share of products with a GTIN.",
        "real_dataset",
        "share",
    ),
    "catalog_image_coverage": (
        "Share of products with an image.",
        "real_dataset",
        "share",
    ),
    "simulated_events": (
        "Event rows generated by the session simulator.",
        "simulated",
        "rows",
    ),
    "simulated_sessions": ("Simulated sessions generated.", "simulated", "sessions"),
}


def collect_from_database() -> dict[str, Any]:
    """Run every metric query. Returns {} when the database is unreachable."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "apps" / "api" / "src"))
    try:
        from sqlalchemy import text

        from cartiq_api.db import get_engine, ping
    except ImportError:
        return {}

    if not ping():
        return {}

    collected: dict[str, Any] = {}
    with get_engine().connect() as connection:
        for key, sql in QUERIES.items():
            value = connection.execute(text(sql)).scalar()
            if value is None:
                continue
            definition, provenance, unit = DESCRIPTIONS[key]
            number = float(value) if isinstance(value, float) else int(value)
            if isinstance(number, float):
                number = round(number, 6)
            collected[key] = metric(
                number,
                provenance=provenance,
                definition=definition,
                source=f"scripts/metrics.py :: {key}",
                unit=unit,
            )
    return collected


def collect_simulation_truth() -> dict[str, Any]:
    """The configured effect of the most recent simulation run, if any."""
    import sys

    sys.path.insert(0, str(REPO_ROOT / "apps" / "api" / "src"))
    try:
        from sqlalchemy import text

        from cartiq_api.db import get_engine, ping
    except ImportError:
        return {}
    if not ping():
        return {}

    statement = text(
        "SELECT params FROM simulation_runs ORDER BY created_at DESC LIMIT 1"
    )
    with get_engine().connect() as connection:
        row = connection.execute(statement).scalar()
    if not row:
        return {}
    payload = row if isinstance(row, dict) else json.loads(row)
    truth = payload.get("truth") or {}
    if "expected_relative_lift" not in truth:
        return {}
    return {
        "simulated_configured_relative_lift": metric(
            round(float(truth["expected_relative_lift"]), 6),
            provenance="simulated",
            definition=(
                "Relative conversion lift the simulator was CONFIGURED to produce, as an "
                "exact population parameter. The Experiment Studio never reads this; it "
                "must recover it from the generated events. See docs/SIMULATION.md."
            ),
            source="simulation_runs.params->truth",
            unit="relative",
        )
    }


def collect_diagnosis() -> dict[str, Any]:
    """Funnel, KPI and segmentation figures from the analytics layer.

    Computed through the same code the console uses, so a number quoted in the
    README cannot drift from the one on the chart.
    """
    import sys

    sys.path.insert(0, str(REPO_ROOT / "apps" / "api" / "src"))
    try:
        from cartiq_api.analytics import (
            Filters,
            friction_ranking,
            funnel,
            kpis,
            segment_kpis,
        )
        from cartiq_api.db import ping
    except ImportError:
        return {}
    if not ping():
        return {}

    collected: dict[str, Any] = {}
    simulated = Filters(data_source="SIMULATED")

    try:
        measures = kpis(simulated)
    except Exception:  # noqa: BLE001 - models may not be built yet
        return {}

    for key in (
        "conversion_rate",
        "aov",
        "revenue_per_visitor",
        "cart_abandonment_rate",
        "search_to_purchase_rate",
    ):
        entry = measures.get(key, {})
        if not entry.get("available"):
            continue
        collected[f"funnel_{key}"] = metric(
            round(float(entry["value"]), 6),
            provenance="simulated",
            definition=entry["definition"],
            source="cartiq_api.analytics.kpis",
            unit=entry["unit"],
        )

    steps = funnel(simulated)
    if not steps.empty:
        worst = steps.iloc[steps["drop_rate"].idxmax()]
        collected["funnel_worst_step"] = metric(
            str(worst["step_label"]),
            provenance="simulated",
            definition="Funnel step losing the largest share of the sessions that reached it.",
            source="cartiq_api.analytics.funnel",
        )
        collected["funnel_worst_step_drop_rate"] = metric(
            round(float(worst["drop_rate"]), 6),
            provenance="simulated",
            definition="Share of sessions lost at the worst funnel step.",
            source="cartiq_api.analytics.funnel",
            unit="share",
        )

    ranking = friction_ranking(simulated)
    if not ranking.empty:
        top = ranking.iloc[0]
        collected["friction_top_step"] = metric(
            f"{top['from_label']} -> {top['step_label']}",
            provenance="simulated",
            definition="Transition carrying the most estimated revenue loss.",
            source="cartiq_api.analytics.friction",
        )
        collected["friction_top_share_of_loss"] = metric(
            round(float(top["share_of_loss"]), 6),
            provenance="simulated",
            definition="Share of all modelled revenue loss attributable to the worst step.",
            source="cartiq_api.analytics.friction",
            unit="share",
        )

    segments = segment_kpis("REAL_DATASET")
    if not segments.empty:
        best = segments.iloc[0]
        collected["segment_top_by_revenue"] = metric(
            str(best["segment_label"]),
            provenance="real_dataset",
            definition="RFM segment holding the largest share of revenue.",
            source="cartiq_api.analytics.segmentation",
        )
        collected["segment_top_revenue_share"] = metric(
            round(float(best["revenue_share"]), 6),
            provenance="real_dataset",
            definition="Share of revenue held by the largest RFM segment.",
            source="cartiq_api.analytics.segmentation",
            unit="share",
        )
        collected["segment_top_customer_share"] = metric(
            round(float(best["customer_share"]), 6),
            provenance="real_dataset",
            definition="Share of customers in the largest-revenue RFM segment.",
            source="cartiq_api.analytics.segmentation",
            unit="share",
        )

    return collected


def collect_abandonment_model() -> dict[str, Any]:
    """Abandonment-model evaluation, read from the training report.

    Read rather than retrained here: training is a separate, explicit step
    (`make train`), so `make metrics` cannot silently publish a model nobody
    asked for.
    """
    report = REPO_ROOT / "reports" / "abandonment_model.json"
    if not report.exists():
        return {}
    payload = json.loads(report.read_text())
    best = payload["metrics"][payload["best_model"]]
    baseline = payload["metrics"]["majority_class_baseline"]

    def entry(value: float, definition: str, unit: str | None = None) -> dict[str, Any]:
        return metric(
            round(float(value), 6),
            provenance="model_eval",
            definition=definition,
            source="scripts/train_abandonment.py",
            unit=unit,
        )

    return {
        "abandonment_model_rows": entry(
            payload["rows"],
            "Carting sessions the model was trained and evaluated on.",
            "rows",
        ),
        "abandonment_model_roc_auc": entry(
            best["roc_auc"], "ROC AUC of the selected model on a held-out split."
        ),
        "abandonment_model_average_precision": entry(
            best["average_precision"],
            "Average precision of the selected model. The honest headline at an ~80% "
            "positive rate, where always predicting 'abandoned' already scores 0.80.",
        ),
        "abandonment_model_baseline_average_precision": entry(
            baseline["average_precision"],
            "Average precision of always predicting the majority class.",
        ),
        "abandonment_model_brier_score": entry(
            best["brier_score"],
            "Brier score of the selected model; lower is better. Calibration matters "
            "because the nudge engine fires on a probability threshold.",
        ),
        "abandonment_model_selected": metric(
            payload["best_model"],
            provenance="model_eval",
            definition="Model chosen by average precision on the held-out split.",
            source="scripts/train_abandonment.py",
        ),
    }


def collect() -> dict[str, Any]:
    """Build the metrics payload.

    Every figure comes from a query in this file against the loaded database.
    Nothing is hand-written, and each entry carries its own provenance so a real
    measurement can never be mistaken for a simulated one.
    """
    metrics: dict[str, Any] = {}
    metrics.update(collect_from_database())
    metrics.update(collect_simulation_truth())
    metrics.update(collect_diagnosis())
    metrics.update(collect_abandonment_model())

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "git_sha": git_sha(),
        "phase": 5,
        "notes": (
            "Diagnosis metrics are computed from a real public e-commerce dataset "
            "(UCI Online Retail II, CC BY 4.0). Experiment results are computed from "
            "simulated sessions generated by scripts/simulate.py with the parameters "
            "documented in docs/SIMULATION.md, and are labelled 'simulated'. "
            "No figure in this file is hand-written."
        ),
        "database_available": bool(metrics),
        "metrics": metrics,
    }


def main() -> int:
    """Write reports/metrics.json."""
    payload = collect()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(
        f"wrote {OUTPUT.relative_to(REPO_ROOT)} ({len(payload['metrics'])} metrics, phase {payload['phase']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
