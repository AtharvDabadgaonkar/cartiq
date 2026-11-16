"""COPY loading against a real database.

Skipped when Postgres is unreachable, so the unit suite still runs offline. CI
provides a Postgres service, so this does run there.

Everything written here uses a dedicated key prefix and is removed afterwards,
so the test never disturbs a developer's loaded data.
"""

import pandas as pd
import pytest
from sqlalchemy import text

from cartiq_api.db import get_engine, ping
from cartiq_api.loaders import (
    deterministic_id,
    load_events,
    load_products,
    load_returns,
    psycopg_connection,
)


def _schema_ready() -> bool:
    """True when Postgres is up AND the migrations have been applied."""
    if not ping():
        return False
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1 FROM events LIMIT 1"))
        return True
    except Exception:  # a missing table is a skip, not a failure
        return False


pytestmark = pytest.mark.skipif(not _schema_ready(), reason="database unreachable or not migrated")

KEY_PREFIX = "pytest-loaders"
PRODUCT_ID = "pytest-sku-1"


@pytest.fixture
def connection():
    with psycopg_connection() as conn:
        yield conn
        # Children first: events reference products.
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM events WHERE product_id = %s", (PRODUCT_ID,))
            cursor.execute("DELETE FROM events WHERE session_id LIKE %s", (f"{KEY_PREFIX}%",))
            cursor.execute("DELETE FROM return_lines WHERE order_id LIKE %s", (f"{KEY_PREFIX}%",))
            cursor.execute("DELETE FROM products WHERE id = %s", (PRODUCT_ID,))
        conn.commit()


def catalog_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "product_id": PRODUCT_ID,
                "title": "Pytest Red Glass Bauble",
                "description": None,
                "brand": None,
                "category": "seasonal",
                "category_path": "seasonal.christmas",
                "price": 4.25,
                "currency": "GBP",
                "image_url": None,
                "gtin": None,
                "in_stock": True,
                "attributes": {"colour": ["Red"], "material": ["Glass"]},
                "generated": True,
                "generated_fields": ["category", "attributes.colour"],
            }
        ]
    )


def events_frame() -> pd.DataFrame:
    base = {
        "user_id": "pytest-user",
        "session_id": f"{KEY_PREFIX}-session",
        "device": "unknown",
        "traffic_source": "unknown",
        "is_new_user": None,
        "page": None,
        "experiment_assignments": {},
        "properties": {"order_id": "pytest-1"},
    }
    return pd.DataFrame(
        [
            {
                **base,
                "event_type": "session_start",
                "timestamp": pd.Timestamp("2026-03-01T12:00:00Z"),
                "product_id": None,
                "price": None,
                "quantity": None,
            },
            {
                **base,
                "event_type": "purchase",
                "timestamp": pd.Timestamp("2026-03-01T12:00:05Z"),
                "product_id": PRODUCT_ID,
                "price": 4.25,
                "quantity": 3,
            },
        ]
    )


def test_products_load_with_json_and_array_columns(connection):
    assert load_products(connection, catalog_frame()) == 1

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT attributes, generated_fields, brand, gtin FROM products WHERE id = %s",
            (PRODUCT_ID,),
        )
        attributes, generated_fields, brand, gtin = cursor.fetchone()

    # jsonb and text[] are different column types and are rendered differently.
    assert attributes == {"colour": ["Red"], "material": ["Glass"]}
    assert generated_fields == ["category", "attributes.colour"]
    # Unobservable fields must arrive as NULL, not as empty strings.
    assert brand is None
    assert gtin is None


def test_events_load_and_are_idempotent(connection):
    load_products(connection, catalog_frame())
    first = load_events(connection, events_frame(), source="REAL_DATASET", key_prefix=KEY_PREFIX)
    assert first == 2

    # Re-running an import must be a no-op, not a duplicate or an error.
    second = load_events(connection, events_frame(), source="REAL_DATASET", key_prefix=KEY_PREFIX)
    assert second == 0

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM events WHERE session_id = %s", (f"{KEY_PREFIX}-session",)
        )
        assert cursor.fetchone()[0] == 2


def test_nullable_columns_round_trip(connection):
    load_products(connection, catalog_frame())
    load_events(connection, events_frame(), source="REAL_DATASET", key_prefix=KEY_PREFIX)

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT page, is_new_user, device::text, quantity FROM events "
            "WHERE session_id = %s AND event_type = 'purchase'",
            (f"{KEY_PREFIX}-session",),
        )
        page, is_new_user, device, quantity = cursor.fetchone()

    assert page is None
    assert is_new_user is None
    assert device == "unknown"
    # A float "3.0" would be rejected by the integer column.
    assert quantity == 3


def test_returns_load_with_their_import(connection):
    import_id = deterministic_id("dataset_import", KEY_PREFIX)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO dataset_imports (
                id, source, name, url, licence, attribution, rows_read, rows_loaded,
                rows_dropped, products_loaded, returns_loaded, observable_steps
            ) VALUES (%s,'pytest','pytest','http://x','CC BY 4.0','x',0,0,'{}',0,0,'{}')
            ON CONFLICT (id) DO NOTHING
            """,
            (import_id,),
        )
    connection.commit()

    returns = pd.DataFrame(
        [
            {
                "order_id": f"{KEY_PREFIX}-C1",
                "user_id": "pytest-user",
                "product_id": None,
                "quantity": 2,
                "unit_price": 4.25,
                "occurred_at": pd.Timestamp("2026-03-02T09:00:00Z"),
            }
        ]
    )
    assert (
        load_returns(connection, returns, dataset_import_id=import_id, key_prefix=KEY_PREFIX) == 1
    )
    assert (
        load_returns(connection, returns, dataset_import_id=import_id, key_prefix=KEY_PREFIX) == 0
    )

    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM return_lines WHERE dataset_import_id = %s", (import_id,))
        cursor.execute("DELETE FROM dataset_imports WHERE id = %s", (import_id,))
    connection.commit()


def test_empty_frames_load_nothing(connection):
    assert load_products(connection, pd.DataFrame()) == 0
    assert load_events(connection, pd.DataFrame(), source="SIMULATED", key_prefix=KEY_PREFIX) == 0
    assert (
        load_returns(
            connection,
            pd.DataFrame(),
            dataset_import_id=deterministic_id("x"),
            key_prefix=KEY_PREFIX,
        )
        == 0
    )
