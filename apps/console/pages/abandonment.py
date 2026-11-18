"""Cart abandonment: the risk model and the nudge engine it drives."""

from __future__ import annotations

from types import SimpleNamespace

import altair as alt
import pandas as pd
import streamlit as st

from cartiq_api.ml import train_abandonment_model
from cartiq_api.ml.abandonment import NotEnoughDataError
from cartiq_api.nudges import (
    HIGH_RISK_THRESHOLD,
    MEDIUM_RISK_THRESHOLD,
    describe_rules,
)
from cartiq_console.controls import empty_state, snapshot_notice
from cartiq_console.source import abandonment_payload, is_snapshot
from cartiq_console.theme import AMBER, CLAY, MOSS, data_source_badge

st.title("Abandonment")
data_source_badge("simulated")
st.caption(
    "The model is trained on simulated sessions, because the real dataset contains no "
    "abandoned carts at all — it records completed orders only. Everything here is labelled "
    "simulated and is not a real-world result."
)


@st.cache_resource(show_spinner="Training the abandonment model…")
def trained():
    """Train once per process; the result is deterministic for a fixed seed."""
    return train_abandonment_model()


if is_snapshot():
    snapshot_notice()
    payload = abandonment_payload()
    if payload is None:
        empty_state("The committed snapshot has no model evaluation.")
        st.stop()
    if "error" in payload:
        # The export recorded why training was refused, so the page can say so
        # instead of looking broken.
        empty_state(payload["error"])
        st.stop()
    result = SimpleNamespace(
        rows=int(payload["rows"]),
        positive_rate=float(payload["positive_rate"]),
        best_model=str(payload["best_model"]),
        metrics=payload["metrics"],
        calibration=pd.DataFrame(payload["calibration"]),
        feature_importance=pd.DataFrame(payload["feature_importance"]),
    )
else:
    try:
        result = trained()
    except NotEnoughDataError as error:
        empty_state(f"{error}")
        st.stop()

metrics = pd.DataFrame(result.metrics).T
best = result.metrics[result.best_model]
baseline = result.metrics["majority_class_baseline"]

a, b, c, d = st.columns(4)
a.metric("Carts", f"{result.rows:,}")
b.metric("Abandoned", f"{result.positive_rate:.1%}")
c.metric("ROC AUC", f"{best['roc_auc']:.3f}", help="0.5 is a coin flip.")
d.metric(
    "Average precision",
    f"{best['average_precision']:.3f}",
    delta=f"{best['average_precision'] - baseline['average_precision']:+.3f} vs baseline",
    help=(
        "With an ~80% abandonment rate, average precision is the honest headline: always "
        "predicting 'abandoned' already scores 0.80."
    ),
)

st.subheader("Model comparison")
st.caption(
    "A logistic baseline and a gradient-boosted model, scored on the same held-out split, "
    "against the majority-class baseline."
)
st.dataframe(
    metrics.reset_index().rename(
        columns={
            "index": "Model",
            "roc_auc": "ROC AUC",
            "average_precision": "Avg precision",
            "precision": "Precision",
            "recall": "Recall",
            "f1": "F1",
            "brier_score": "Brier (lower better)",
        }
    ),
    hide_index=True,
    use_container_width=True,
)

if result.best_model == "logistic_regression":
    st.info(
        "The gradient-boosted model did **not** beat the logistic baseline here. That is a "
        "finding, not a failure: the simulator generates abandonment from additive device, "
        "segment and channel effects, so there is little non-linear structure to find. "
        "Shipping the simpler model is the right call.",
        icon=":material/lightbulb:",
    )

# --- Calibration -----------------------------------------------------------
st.subheader("Calibration")
st.caption(
    "The nudge engine fires on a **threshold** of predicted risk, so the probability has to "
    "mean what it says. A model that ranks well but is badly calibrated would nudge the "
    "wrong carts. Points on the diagonal are well calibrated."
)

calibration = result.calibration
diagonal = pd.DataFrame({"x": [0.0, 1.0], "y": [0.0, 1.0]})
reference = (
    alt.Chart(diagonal)
    .mark_line(strokeDash=[4, 4], color="#888")
    .encode(
        x=alt.X("x:Q", title="Predicted risk"), y=alt.Y("y:Q", title="Observed rate")
    )
)
points = (
    alt.Chart(calibration)
    .mark_circle(color=AMBER)
    .encode(
        x=alt.X("predicted:Q", scale=alt.Scale(domain=[0, 1])),
        y=alt.Y("observed:Q", scale=alt.Scale(domain=[0, 1])),
        size=alt.Size("count:Q", title="Carts in bin"),
        tooltip=[
            alt.Tooltip("predicted:Q", format=".3f", title="Predicted"),
            alt.Tooltip("observed:Q", format=".3f", title="Observed"),
            alt.Tooltip("count:Q", format=",", title="Carts"),
        ],
    )
)
st.altair_chart((reference + points).properties(height=300), use_container_width=True)
st.caption(
    f"Brier score {best['brier_score']:.4f} — lower is better; 0.25 is uninformative."
)

# --- Feature importance ----------------------------------------------------
st.subheader("What the model relies on")
st.caption(
    "Permutation importance on the held-out split, so it measures what the model actually "
    "uses rather than what it was given. Direction comes from the logistic coefficients."
)

importance = result.feature_importance.head(10)
bars = (
    alt.Chart(importance)
    .mark_bar(cornerRadiusEnd=3)
    .encode(
        y=alt.Y("feature:N", sort="-x", title=None),
        x=alt.X("importance:Q", title="Drop in average precision when shuffled"),
        color=alt.Color(
            "pushes:N",
            title="Pushes",
            scale=alt.Scale(
                domain=["toward abandoning", "toward buying"], range=[CLAY, MOSS]
            ),
        ),
        tooltip=["feature", "importance", "pushes"],
    )
    .properties(height=280)
)
st.altair_chart(bars, use_container_width=True)

st.caption(
    "No post-cart feature appears here by construction: `mart_cart_sessions` excludes every "
    "funnel step after the cart is created. A model that knew the shopper reached payment "
    "would score beautifully and be undeployable."
)

# --- Nudge engine ----------------------------------------------------------
st.divider()
st.subheader("Nudge engine")
st.caption(
    f"Rules, not a model. At most one nudge per cart: stacking messages turns a helpful "
    f"nudge into a dark pattern, and it would make the experiment uninterpretable. "
    f"Nothing fires below {MEDIUM_RISK_THRESHOLD:.0%} risk; the lower-pressure message takes "
    f"over above {HIGH_RISK_THRESHOLD:.0%}."
)
st.dataframe(
    pd.DataFrame(describe_rules()).rename(
        columns={
            "order": "#",
            "nudge": "Nudge",
            "flag": "Feature flag",
            "condition": "Fires when",
            "message": "What it says",
        }
    ),
    hide_index=True,
    use_container_width=True,
)
st.caption(
    "Each nudge sits behind its own feature flag, so it can be ramped or killed without "
    "touching the others or retraining anything. Phase 7 attaches them to the flagship "
    "experiment."
)
