"""Bulk loading of cleaned frames into Postgres.

Uses COPY rather than INSERT: the real dataset is ~1.08M event rows, which
takes seconds this way and minutes otherwise.

Event ids are deterministic UUIDv5 values derived from the source's natural key,
so re-running an ingest is idempotent — the same source row always produces the
same event id, and `ON CONFLICT DO NOTHING` makes a repeat run a no-op.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from collections.abc import Iterable, Sequence
from typing import Any

import pandas as pd
import psycopg
from sqlalchemy import text

from cartiq_api.config import get_settings
from cartiq_api.db import get_engine

#: Fixed namespace for deterministic event ids. Changing it re-keys every row.
CARTIQ_NAMESPACE = uuid.UUID("6f1b8c2e-0000-5000-8000-000000000001")

EVENT_COLUMNS: tuple[str, ...] = (
    "event_id",
    "event_type",
    "timestamp",
    "user_id",
    "session_id",
    "device",
    "traffic_source",
    "is_new_user",
    "page",
    "product_id",
    "price",
    "quantity",
    "experiment_assignments",
    "properties",
    "source",
    "simulation_run_id",
)

PRODUCT_COLUMNS: tuple[str, ...] = (
    "id",
    "title",
    "description",
    "brand",
    "category",
    "category_path",
    "price",
    "currency",
    "image_url",
    "gtin",
    "in_stock",
    "attributes",
    "generated",
    "generated_fields",
    # Prisma maintains @updatedAt in the client, so the column is NOT NULL with
    # no database default and COPY has to supply it.
    "updated_at",
)

RETURN_COLUMNS: tuple[str, ...] = (
    "id",
    "order_id",
    "original_order_id",
    "user_id",
    "product_id",
    "quantity",
    "unit_price",
    "occurred_at",
    "source",
    "dataset_import_id",
)


def deterministic_id(*parts: object) -> str:
    """UUIDv5 over a natural key, so the same source row keeps the same id."""
    return str(uuid.uuid5(CARTIQ_NAMESPACE, "|".join(str(p) for p in parts)))


def psycopg_connection() -> psycopg.Connection[Any]:
    """Open a raw psycopg connection, which COPY needs."""
    dsn = get_settings().database_url.split("?")[0]
    return psycopg.connect(dsn)


def _to_pg_array(values: Any) -> str:
    """Render a Python list as a Postgres array literal, e.g. {"a","b"}.

    Array columns are not JSON columns: COPY rejects `["a","b"]` for text[].
    """
    if values is None:
        return "{}"
    escaped = [str(v).replace("\\", "\\\\").replace('"', '\\"') for v in values]
    return "{" + ",".join(f'"{v}"' for v in escaped) + "}"


def _to_pg(value: Any) -> Any:
    """Render one Python value for COPY ... FROM STDIN WITH CSV."""
    if value is None or value is pd.NaT or (isinstance(value, float) and pd.isna(value)):
        return None
    if value is pd.NA:
        return None
    if isinstance(value, dict | list):
        return json.dumps(value, separators=(",", ":"), default=str)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def copy_frame(
    connection: psycopg.Connection[Any],
    table: str,
    columns: Sequence[str],
    rows: Iterable[Sequence[Any]],
    *,
    array_columns: Sequence[str] = (),
    batch_size: int = 50_000,
) -> int:
    """COPY rows into a staging table, then merge, skipping existing keys.

    A temporary table plus `INSERT ... ON CONFLICT DO NOTHING` is used instead of
    COPY straight into the target, because COPY has no conflict handling and a
    re-run must not fail on rows that are already there.
    """
    column_list = ", ".join(f'"{c}"' for c in columns)
    staging = f"staging_{table}"
    total = 0
    array_indexes = {columns.index(name) for name in array_columns if name in columns}

    with connection.cursor() as cursor:
        cursor.execute(
            f'CREATE TEMP TABLE "{staging}" ' f'(LIKE "{table}" INCLUDING DEFAULTS) ON COMMIT DROP'
        )

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        pending = 0

        def flush() -> None:
            nonlocal pending
            if not pending:
                return
            buffer.seek(0)
            with cursor.copy(
                f"COPY \"{staging}\" ({column_list}) FROM STDIN WITH (FORMAT CSV, NULL '\\N')"
            ) as copy:
                copy.write(buffer.read())
            buffer.seek(0)
            buffer.truncate(0)
            pending = 0

        for row in rows:
            rendered = []
            for index, value in enumerate(row):
                if index in array_indexes:
                    rendered.append(_to_pg_array(value))
                    continue
                converted = _to_pg(value)
                rendered.append("\\N" if converted is None else converted)
            writer.writerow(rendered)
            pending += 1
            total += 1
            if pending >= batch_size:
                flush()
        flush()

        # Primary key is the first column for every table loaded here.
        cursor.execute(
            f'INSERT INTO "{table}" ({column_list}) '
            f'SELECT {column_list} FROM "{staging}" '
            f'ON CONFLICT ("{columns[0]}") DO NOTHING'
        )
        inserted = cursor.rowcount

    connection.commit()
    return inserted if inserted >= 0 else total


def load_products(connection: psycopg.Connection[Any], catalog: pd.DataFrame) -> int:
    """Insert catalog rows, leaving existing products untouched."""
    if catalog.empty:
        return 0
    frame = catalog.rename(columns={"product_id": "id"})
    frame["updated_at"] = pd.Timestamp.now(tz="UTC")
    rows = (tuple(row) for row in frame[list(PRODUCT_COLUMNS)].itertuples(index=False, name=None))
    return copy_frame(
        connection, "products", PRODUCT_COLUMNS, rows, array_columns=("generated_fields",)
    )


def load_events(
    connection: psycopg.Connection[Any],
    events: pd.DataFrame,
    *,
    source: str,
    key_prefix: str,
    simulation_run_id: str | None = None,
) -> int:
    """Insert events, assigning deterministic ids from the natural key.

    Args:
        connection: Open psycopg connection.
        events: Cleaned event frame.
        source: DataSource enum value, e.g. "REAL_DATASET".
        key_prefix: Namespace for the natural key, so two sources cannot collide.
        simulation_run_id: Set for simulated batches.
    """
    if events.empty:
        return 0

    frame = events.copy()
    if "event_id" not in frame.columns:
        # Natural key: session + type + product + position within that group.
        occurrence = frame.groupby(
            ["session_id", "event_type", "product_id"], dropna=False
        ).cumcount()
        frame["event_id"] = [
            deterministic_id(key_prefix, session, event_type, product, index)
            for session, event_type, product, index in zip(
                frame["session_id"],
                frame["event_type"],
                frame["product_id"],
                occurrence,
                strict=True,
            )
        ]

    # A column holding NaN for the events that have no quantity gets upcast to
    # float, and COPY will not accept "1.0" for an integer column.
    if "quantity" in frame.columns:
        frame["quantity"] = frame["quantity"].astype("Int64")

    frame["experiment_assignments"] = frame.get(
        "experiment_assignments", pd.Series([{}] * len(frame), index=frame.index)
    )
    frame["source"] = source
    frame["simulation_run_id"] = simulation_run_id

    rows = (tuple(row) for row in frame[list(EVENT_COLUMNS)].itertuples(index=False, name=None))
    return copy_frame(connection, "events", EVENT_COLUMNS, rows)


def load_returns(
    connection: psycopg.Connection[Any],
    returns: pd.DataFrame,
    *,
    dataset_import_id: str,
    key_prefix: str,
) -> int:
    """Insert return lines for the Phase 7 return-rate guardrail."""
    if returns.empty:
        return 0
    frame = returns.copy()
    occurrence = frame.groupby(["order_id", "product_id"], dropna=False).cumcount()
    frame["id"] = [
        deterministic_id(key_prefix, "return", order, product, index)
        for order, product, index in zip(
            frame["order_id"], frame["product_id"], occurrence, strict=True
        )
    ]
    frame["original_order_id"] = None
    frame["source"] = "REAL_DATASET"
    frame["dataset_import_id"] = dataset_import_id
    rows = (tuple(row) for row in frame[list(RETURN_COLUMNS)].itertuples(index=False, name=None))
    return copy_frame(connection, "return_lines", RETURN_COLUMNS, rows)


def table_counts() -> dict[str, int]:
    """Row counts for the tables the ingest and simulate scripts report on."""
    statement = text(
        """
        SELECT
            (SELECT count(*) FROM events)                               AS events,
            (SELECT count(*) FROM events WHERE source = 'REAL_DATASET') AS real_events,
            (SELECT count(*) FROM events WHERE source = 'SIMULATED')    AS simulated_events,
            (SELECT count(*) FROM products)                             AS products,
            (SELECT count(*) FROM return_lines)                         AS return_lines,
            (SELECT count(*) FROM dataset_imports)                      AS dataset_imports,
            (SELECT count(*) FROM simulation_runs)                      AS simulation_runs
        """
    )
    with get_engine().connect() as connection:
        row = connection.execute(statement).mappings().one()
    return {key: int(value) for key, value in row.items()}


#: Materialised views, in dependency order. Refreshing a stale one is cheaper
#: than rebuilding every model, and a load that skips it would leave the console
#: showing the previous dataset.
MATERIALISED_VIEWS: tuple[str, ...] = ("int_sessions", "int_orders", "mart_funnel")


def refresh_materialised_views() -> list[str]:
    """Refresh the materialised views after a data load.

    Returns the names refreshed. Views that do not exist yet are skipped, so a
    load against an unmigrated database still succeeds.
    """
    refreshed: list[str] = []
    with get_engine().begin() as connection:
        for view in MATERIALISED_VIEWS:
            exists = connection.execute(
                text("SELECT to_regclass(:name) IS NOT NULL"), {"name": view}
            ).scalar()
            if not exists:
                continue
            connection.execute(text(f"REFRESH MATERIALIZED VIEW {view}"))
            refreshed.append(view)
        if refreshed:
            connection.execute(text("ANALYZE"))
    return refreshed
