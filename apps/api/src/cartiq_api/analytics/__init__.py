"""Diagnosis analytics: funnel, KPIs, segmentation and friction.

One implementation, used by the Streamlit console, the metrics script and the
tests, so a figure cannot mean one thing on a chart and another in a report.
"""

from cartiq_api.analytics.filters import Filters
from cartiq_api.analytics.friction import friction_ranking
from cartiq_api.analytics.funnel import FUNNEL_STEPS, funnel, funnel_by_dimension
from cartiq_api.analytics.kpis import KPI_DEFINITIONS, kpis
from cartiq_api.analytics.segmentation import (
    RFM_SEGMENTS,
    behavioural_clusters,
    rfm_segments,
    segment_kpis,
)

__all__ = [
    "FUNNEL_STEPS",
    "KPI_DEFINITIONS",
    "RFM_SEGMENTS",
    "Filters",
    "behavioural_clusters",
    "friction_ranking",
    "funnel",
    "funnel_by_dimension",
    "kpis",
    "rfm_segments",
    "segment_kpis",
]
