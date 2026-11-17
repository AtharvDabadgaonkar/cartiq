#!/usr/bin/env python3
"""Train the cart-abandonment risk model and export it.

    python scripts/train_abandonment.py

Writes:
  reports/abandonment_model.json              full evaluation
  apps/web/lib/model/abandonment-model.json   coefficients the storefront scores with

The storefront cannot run scikit-learn, so the logistic model is exported as
plain numbers. One trained model, two runtimes.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "apps" / "api" / "src"))

from cartiq_api.ml import train_abandonment_model  # noqa: E402
from cartiq_api.ml.abandonment import NotEnoughDataError, export_logistic_model  # noqa: E402

REPORT = REPO_ROOT / "reports" / "abandonment_model.json"
WEB_MODEL = REPO_ROOT / "apps" / "web" / "lib" / "model" / "abandonment-model.json"


def main() -> int:
    """Train, evaluate and export."""
    try:
        result = train_abandonment_model()
    except NotEnoughDataError as error:
        print(f"cannot train: {error}")
        return 1

    print(f"carts            {result.rows:,}")
    print(f"abandonment rate {result.positive_rate:.1%}")
    print()
    for name, metrics in result.metrics.items():
        print(
            f"  {name:<26} auc={metrics['roc_auc']:.3f} "
            f"ap={metrics['average_precision']:.3f} brier={metrics['brier_score']:.4f}"
        )
    print(f"\nbest by average precision: {result.best_model}")
    if result.best_model == "logistic_regression":
        print(
            "  the boosted model did not beat the baseline; the complexity is not earning its keep"
        )

    print("\ntop features:")
    for _, row in result.feature_importance.head(5).iterrows():
        print(f"  {row['feature']:<22} {row['importance']:+.4f}  {row['pushes']}")

    print("\ncalibration (predicted vs observed):")
    for _, row in result.calibration.iterrows():
        print(
            f"  {row['bin_lower']:.1f}-{row['bin_upper']:.1f}  "
            f"predicted {row['predicted']:.3f}  observed {row['observed']:.3f}  "
            f"n={int(row['count']):,}"
        )

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        json.dumps(
            {
                **result.summary(),
                "calibration": result.calibration.to_dict(orient="records"),
                "feature_importance": result.feature_importance.to_dict(
                    orient="records"
                ),
            },
            indent=2,
        )
        + "\n"
    )

    WEB_MODEL.parent.mkdir(parents=True, exist_ok=True)
    WEB_MODEL.write_text(json.dumps(export_logistic_model(result), indent=2) + "\n")

    print(f"\nwrote {REPORT.relative_to(REPO_ROOT)}")
    print(f"wrote {WEB_MODEL.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
