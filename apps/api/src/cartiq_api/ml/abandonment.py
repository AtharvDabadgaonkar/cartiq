"""Cart-abandonment risk model.

Predicts, at the moment a cart is created, whether it will be abandoned.

Two things matter more than the headline AUC:

1. **No leakage.** Features come from `mart_cart_sessions`, which deliberately
   excludes every post-cart funnel step. A model that knows the shopper reached
   the payment step would score beautifully and be useless, because by then the
   decision is already made.
2. **Calibration, not just ranking.** The nudge engine switches on a *threshold*
   of predicted risk, so the probability has to mean what it says. A model with
   good AUC and bad calibration would fire nudges at the wrong carts, so the
   Brier score and a reliability curve are reported alongside AUC.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer  # type: ignore[import-untyped]
from sklearn.ensemble import HistGradientBoostingClassifier  # type: ignore[import-untyped]
from sklearn.inspection import permutation_importance  # type: ignore[import-untyped]
from sklearn.linear_model import LogisticRegression  # type: ignore[import-untyped]
from sklearn.metrics import (  # type: ignore[import-untyped]
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split  # type: ignore[import-untyped]
from sklearn.pipeline import Pipeline  # type: ignore[import-untyped]
from sklearn.preprocessing import OneHotEncoder, StandardScaler  # type: ignore[import-untyped]
from sqlalchemy import text

from cartiq_api.db import get_engine

CATEGORICAL_FEATURES: tuple[str, ...] = ("device", "traffic_source", "segment")
NUMERIC_FEATURES: tuple[str, ...] = (
    "cart_value",
    "cart_items",
    "cart_lines",
    "product_views",
    "cart_adds",
    "seconds_to_cart",
    "hour_of_day",
    "day_of_week",
    "gap_to_free_shipping",
)
BOOLEAN_FEATURES: tuple[str, ...] = ("is_new_user", "used_search", "pays_shipping")

TARGET = "abandoned"

#: Below this, an evaluation is noise dressed as a model.
MIN_TRAINING_ROWS = 2_000


class NotEnoughDataError(RuntimeError):
    """Raised when the loaded data cannot support an honest evaluation."""


@dataclass
class AbandonmentResult:
    """Trained models and their evaluation on a held-out split."""

    metrics: dict[str, dict[str, float]]
    feature_importance: pd.DataFrame
    calibration: pd.DataFrame
    rows: int
    positive_rate: float
    best_model: str
    models: dict[str, Any] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        """JSON-safe summary for reports/metrics.json."""
        return {
            "rows": self.rows,
            "positive_rate": round(self.positive_rate, 6),
            "best_model": self.best_model,
            "metrics": self.metrics,
            "top_features": self.feature_importance.head(8).to_dict(orient="records"),
        }


def load_cart_sessions(data_source: str = "SIMULATED") -> pd.DataFrame:
    """Load the leakage-safe training table."""
    statement = text(
        """
        SELECT abandoned, device, traffic_source, segment, is_new_user, used_search,
               product_views, cart_adds, cart_value::float8 AS cart_value, cart_items,
               cart_lines, seconds_to_cart, hour_of_day, day_of_week, pays_shipping,
               gap_to_free_shipping::float8 AS gap_to_free_shipping
        FROM mart_cart_sessions
        WHERE data_source::text = :data_source
        """
    )
    with get_engine().connect() as connection:
        return pd.read_sql_query(statement, connection, params={"data_source": data_source})


def _build_pipelines(random_state: int) -> dict[str, Pipeline]:
    categorical = list(CATEGORICAL_FEATURES)
    numeric = list(NUMERIC_FEATURES) + list(BOOLEAN_FEATURES)

    preprocessor = ColumnTransformer(
        [
            ("cat", OneHotEncoder(handle_unknown="ignore", drop="first"), categorical),
            ("num", StandardScaler(), numeric),
        ]
    )
    return {
        # The interpretable baseline. If the boosted model cannot beat it, the
        # extra complexity is not earning its keep.
        "logistic_regression": Pipeline(
            [
                ("prep", preprocessor),
                ("clf", LogisticRegression(max_iter=1000, random_state=random_state)),
            ]
        ),
        "gradient_boosting": Pipeline(
            [
                ("prep", preprocessor),
                (
                    "clf",
                    HistGradientBoostingClassifier(
                        max_iter=200, learning_rate=0.1, random_state=random_state
                    ),
                ),
            ]
        ),
    }


def _reliability_curve(y_true: np.ndarray, y_prob: np.ndarray, bins: int = 10) -> pd.DataFrame:
    """Observed vs predicted rate per probability bin.

    Written out rather than using sklearn's calibration_curve so the bin counts
    come back too: a bin holding twelve carts should not be read like one
    holding four thousand.
    """
    edges = np.linspace(0.0, 1.0, bins + 1)
    index = np.clip(np.digitize(y_prob, edges) - 1, 0, bins - 1)
    rows = []
    for b in range(bins):
        mask = index == b
        if not mask.any():
            continue
        rows.append(
            {
                "bin_lower": float(edges[b]),
                "bin_upper": float(edges[b + 1]),
                "predicted": float(y_prob[mask].mean()),
                "observed": float(y_true[mask].mean()),
                "count": int(mask.sum()),
            }
        )
    return pd.DataFrame(rows)


def train_abandonment_model(
    data_source: str = "SIMULATED",
    *,
    test_size: float = 0.25,
    random_state: int = 42,
    threshold: float = 0.5,
) -> AbandonmentResult:
    """Train the baseline and the boosted model, and evaluate both honestly.

    Raises:
        NotEnoughDataError: If there are too few carts, or only one class.
    """
    frame = load_cart_sessions(data_source)
    if len(frame) < MIN_TRAINING_ROWS:
        raise NotEnoughDataError(
            f"{len(frame)} carting sessions is not enough to evaluate a model "
            f"(minimum {MIN_TRAINING_ROWS}). Run `make simulate` to generate more."
        )
    if frame[TARGET].nunique() < 2:
        raise NotEnoughDataError("every cart has the same outcome; nothing to learn")

    features = list(CATEGORICAL_FEATURES) + list(NUMERIC_FEATURES) + list(BOOLEAN_FEATURES)
    x = frame[features].copy()
    for column in BOOLEAN_FEATURES:
        x[column] = x[column].astype(int)
    y = frame[TARGET].astype(int).to_numpy()

    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=test_size, random_state=random_state, stratify=y
    )

    metrics: dict[str, dict[str, float]] = {}
    fitted: dict[str, Any] = {}
    probabilities: dict[str, np.ndarray] = {}

    for name, pipeline in _build_pipelines(random_state).items():
        pipeline.fit(x_train, y_train)
        probability = pipeline.predict_proba(x_test)[:, 1]
        predicted = (probability >= threshold).astype(int)

        metrics[name] = {
            "roc_auc": float(roc_auc_score(y_test, probability)),
            # With an 80% positive rate, average precision is the more honest
            # headline: a model predicting "abandoned" always scores 0.80.
            "average_precision": float(average_precision_score(y_test, probability)),
            "precision": float(precision_score(y_test, predicted, zero_division=0)),
            "recall": float(recall_score(y_test, predicted, zero_division=0)),
            "f1": float(f1_score(y_test, predicted, zero_division=0)),
            "brier_score": float(brier_score_loss(y_test, probability)),
        }
        fitted[name] = pipeline
        probabilities[name] = probability

    best = max(metrics, key=lambda name: metrics[name]["average_precision"])

    # Baseline to compare against: always predict the majority class.
    majority = float(y_test.mean())
    metrics["majority_class_baseline"] = {
        "roc_auc": 0.5,
        "average_precision": majority,
        "precision": majority,
        "recall": 1.0,
        "f1": 2 * majority / (majority + 1),
        "brier_score": float(np.mean((majority - y_test) ** 2)),
    }

    importance = _feature_importance(fitted, x_test, y_test, features, random_state)
    calibration = _reliability_curve(y_test, probabilities[best])

    return AbandonmentResult(
        metrics=metrics,
        feature_importance=importance,
        calibration=calibration,
        rows=len(frame),
        positive_rate=float(y.mean()),
        best_model=best,
        models=fitted,
    )


def _feature_importance(
    fitted: dict[str, Any],
    x_test: pd.DataFrame,
    y_test: np.ndarray,
    features: list[str],
    random_state: int,
) -> pd.DataFrame:
    """Permutation importance on the held-out split.

    Permutation rather than model-internal gain, because it is comparable
    across the two model types and measures what the model actually relies on
    for its held-out predictions.
    """
    result = permutation_importance(
        fitted["gradient_boosting"],
        x_test,
        y_test,
        n_repeats=5,
        random_state=random_state,
        scoring="average_precision",
    )
    frame = pd.DataFrame(
        {
            "feature": features,
            "importance": result.importances_mean,
            "importance_std": result.importances_std,
        }
    )

    # Direction from the interpretable model, so a reader can say which way a
    # feature pushes risk rather than only how much it matters.
    logistic = fitted["logistic_regression"]
    names = list(logistic.named_steps["prep"].get_feature_names_out())
    coefficients = logistic.named_steps["clf"].coef_[0]
    direction: dict[str, float] = {}
    for name, coefficient in zip(names, coefficients, strict=True):
        bare = name.split("__", 1)[-1]
        for feature in features:
            if bare == feature or bare.startswith(f"{feature}_"):
                direction[feature] = direction.get(feature, 0.0) + float(coefficient)

    frame["log_odds"] = frame["feature"].map(direction).fillna(0.0)
    frame["pushes"] = np.where(frame["log_odds"] > 0, "toward abandoning", "toward buying")
    return frame.sort_values("importance", ascending=False).reset_index(drop=True)


def export_logistic_model(result: AbandonmentResult) -> dict[str, Any]:
    """Export the logistic model as plain numbers the storefront can score with.

    The storefront has to score a cart to decide whether to nudge, and shipping
    scikit-learn to a Node runtime is not an option. A logistic regression is
    just an intercept, a set of coefficients, and the one-hot plus standard-scale
    preprocessing — all of which are numbers. Exporting them keeps one trained
    model and two runtimes, rather than two models that drift.

    The boosted model is deliberately NOT exported: it cannot be reduced to
    coefficients, and on this data it does not beat the baseline anyway.
    """
    pipeline = result.models["logistic_regression"]
    prep = pipeline.named_steps["prep"]
    classifier = pipeline.named_steps["clf"]

    encoder = prep.named_transformers_["cat"]
    scaler = prep.named_transformers_["num"]

    numeric = list(NUMERIC_FEATURES) + list(BOOLEAN_FEATURES)
    categories = {
        feature: [str(value) for value in values]
        for feature, values in zip(CATEGORICAL_FEATURES, encoder.categories_, strict=True)
    }

    return {
        "_comment": (
            "Exported logistic abandonment model. Regenerate with "
            "`python scripts/train_abandonment.py`; do not hand-edit."
        ),
        "model": "logistic_regression",
        "trained_on_rows": result.rows,
        "positive_rate": round(result.positive_rate, 6),
        "roc_auc": round(result.metrics["logistic_regression"]["roc_auc"], 6),
        "intercept": float(classifier.intercept_[0]),
        "feature_names": [str(name) for name in prep.get_feature_names_out()],
        "coefficients": [float(c) for c in classifier.coef_[0]],
        "categorical": {
            # drop="first" means the first category is the reference level and
            # has no column of its own.
            "features": list(CATEGORICAL_FEATURES),
            "categories": categories,
            "drop_first": True,
        },
        "numeric": {
            "features": numeric,
            "mean": [float(v) for v in scaler.mean_],
            "scale": [float(v) for v in scaler.scale_],
        },
    }
