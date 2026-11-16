"""Pure loader helpers. The COPY path itself is exercised by the ingest run."""

import pandas as pd
import pytest

from cartiq_api.loaders import (
    EVENT_COLUMNS,
    PRODUCT_COLUMNS,
    _to_pg,
    _to_pg_array,
    deterministic_id,
)


def test_ids_are_deterministic_and_well_formed():
    first = deterministic_id("online-retail-ii", "inv_1", "purchase", "85048", 0)
    assert first == deterministic_id("online-retail-ii", "inv_1", "purchase", "85048", 0)
    assert len(first) == 36


def test_ids_separate_sources():
    # Two sources must never collide on the same natural key.
    assert deterministic_id("a", "inv_1") != deterministic_id("b", "inv_1")


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, None),
        (pd.NaT, None),
        (pd.NA, None),
        (float("nan"), None),
        (True, "true"),
        (False, "false"),
        ({"a": 1}, '{"a":1}'),
        ([1, 2], "[1,2]"),
        (12.5, 12.5),
        ("text", "text"),
    ],
)
def test_value_rendering(value, expected):
    assert _to_pg(value) == expected


def test_timestamps_render_as_iso8601():
    assert _to_pg(pd.Timestamp("2026-03-01T12:00:00Z")) == "2026-03-01T12:00:00+00:00"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, "{}"),
        ([], "{}"),
        (["category"], '{"category"}'),
        (["a", "b"], '{"a","b"}'),
        (['quote"d'], '{"quote\\"d"}'),
    ],
)
def test_array_rendering(value, expected):
    # Array columns are not JSON columns: COPY rejects ["a"] for text[].
    assert _to_pg_array(value) == expected


def test_column_lists_lead_with_the_primary_key():
    # copy_frame resolves conflicts on the first column.
    assert EVENT_COLUMNS[0] == "event_id"
    assert PRODUCT_COLUMNS[0] == "id"


def test_product_columns_supply_updated_at():
    # Prisma maintains @updatedAt client-side, so COPY must provide it.
    assert "updated_at" in PRODUCT_COLUMNS
