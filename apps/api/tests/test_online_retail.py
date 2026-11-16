"""Cleaning rules for the real dataset.

Built on small synthetic frames rather than the 44MB download, so the suite runs
offline and in CI. `test_seed_sample.py` checks the committed real extract.
"""

import pandas as pd
import pytest

from cartiq_api.datasets.online_retail import (
    ONLINE_RETAIL_II,
    clean,
    is_product_code,
)


def raw_frame(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def line(**overrides) -> dict:
    base = {
        "Invoice": "489434",
        "StockCode": "85048",
        "Description": "15CM CHRISTMAS GLASS BALL 20 LIGHTS",
        "Quantity": 12,
        "InvoiceDate": pd.Timestamp("2009-12-01 07:45:00"),
        "Price": 6.95,
        "Customer ID": 13085.0,
        "Country": "United Kingdom",
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("85048", True),
        ("79323P", True),
        ("10002R", True),
        ("POST", False),
        ("DOT", False),
        ("M", False),
        ("BANK CHARGES", False),
        ("AMAZONFEE", False),
        ("ADJUST", False),
        ("gift_0001_20", False),
        ("", False),
    ],
)
def test_product_code_classification(code, expected):
    assert is_product_code(code) is expected


def test_metadata_declares_what_it_cannot_observe():
    # The funnel above `purchase` needs behavioural events this source lacks.
    assert ONLINE_RETAIL_II.observable_steps == ("visit", "purchase")
    assert ONLINE_RETAIL_II.licence == "CC BY 4.0"
    assert "Chen" in ONLINE_RETAIL_II.attribution


def test_clean_reconciles_every_source_row():
    raw = raw_frame(
        [
            line(),
            line(StockCode="79323P", Price=6.75),
            line(StockCode="POST", Description="POSTAGE", Price=18.0),
            line(Quantity=-2),
            line(Price=0.0),
            line(Invoice="C489449", Quantity=-12),
        ]
    )
    result = clean(raw)

    assert result.rows_read == 6
    assert result.dropped["non_product_code"] == 1
    assert result.dropped["non_positive_quantity"] == 1
    assert result.dropped["non_positive_price"] == 1
    assert len(result.returns) == 1
    assert result.reconciles()


def test_unobservable_fields_are_never_invented():
    result = clean(raw_frame([line()]))
    events = result.events
    assert set(events["device"]) == {"unknown"}
    assert set(events["traffic_source"]) == {"unknown"}
    assert events["page"].isna().all()


def test_anonymous_lines_are_kept_with_null_user():
    result = clean(raw_frame([line(**{"Customer ID": float("nan")})]))
    purchases = result.events[result.events["event_type"] == "purchase"]
    assert len(purchases) == 1
    # Kept, not dropped: revenue must still reconcile against the source.
    assert purchases["user_id"].isna().all()
    # And is_new_user stays NULL, because the source cannot say.
    assert purchases["is_new_user"].isna().all()


def test_each_invoice_emits_one_derived_session_start():
    raw = raw_frame(
        [
            line(StockCode="85048"),
            line(StockCode="79323P"),
            line(Invoice="489435", StockCode="22423"),
        ]
    )
    result = clean(raw)
    starts = result.events[result.events["event_type"] == "session_start"]
    assert len(starts) == 2
    assert set(starts["session_id"]) == {"inv_489434", "inv_489435"}
    # Derived rows account for no source row, which is what keeps the
    # reconciliation honest.
    assert (starts["source_row_count"] == 0).all()
    assert all(props["derived"] for props in starts["properties"])


def test_first_invoice_marks_a_new_user():
    raw = raw_frame(
        [
            line(Invoice="1", InvoiceDate=pd.Timestamp("2010-01-01")),
            line(Invoice="2", InvoiceDate=pd.Timestamp("2010-02-01")),
        ]
    )
    purchases = clean(raw).events.query("event_type == 'purchase'").sort_values("timestamp")
    assert list(purchases["is_new_user"]) == [True, False]


def test_products_use_the_modal_description_and_median_price():
    raw = raw_frame(
        [
            line(Description="WIDGET", Price=10.0),
            line(Invoice="2", Description="WIDGET", Price=12.0),
            line(Invoice="3", Description="TYPO WIDGIT", Price=50.0),
        ]
    )
    products = clean(raw).products
    assert len(products) == 1
    assert products.iloc[0]["title"] == "WIDGET"
    assert products.iloc[0]["price"] == 12.0


def test_returns_are_positive_quantities_with_their_own_order_id():
    raw = raw_frame([line(Invoice="C489449", Quantity=-12, Price=6.95)])
    returns = clean(raw).returns
    assert len(returns) == 1
    assert returns.iloc[0]["quantity"] == 12
    assert returns.iloc[0]["unit_price"] == 6.95
    assert returns.iloc[0]["order_id"] == "C489449"


def test_empty_input_produces_empty_typed_frames():
    result = clean(raw_frame([line()]).iloc[0:0])
    assert result.rows_read == 0
    assert result.events.empty
    assert result.products.empty
    assert result.returns.empty
    assert result.reconciles()
