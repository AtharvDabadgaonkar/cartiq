"""Loaders for real public e-commerce datasets.

Each loader returns cleaned DataFrames plus a full account of what was dropped
and why, so an ingested number can always be reconciled against the source file.
"""

from cartiq_api.datasets.base import DatasetMeta, IngestResult
from cartiq_api.datasets.online_retail import ONLINE_RETAIL_II

DATASETS: dict[str, DatasetMeta] = {ONLINE_RETAIL_II.key: ONLINE_RETAIL_II}

__all__ = ["DATASETS", "ONLINE_RETAIL_II", "DatasetMeta", "IngestResult"]
