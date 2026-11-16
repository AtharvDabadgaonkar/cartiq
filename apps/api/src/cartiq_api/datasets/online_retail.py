"""UCI "Online Retail II" loader.

Real transactions from a UK online giftware retailer, Dec 2009 - Dec 2011:
~1.07M invoice lines, 5,942 customers, 5,305 stock codes.

What this source can and cannot tell us
---------------------------------------
It records **purchases**, not browsing. There is no device, no traffic source,
no page and no session beyond the invoice. Rather than fabricate those fields,
the loader writes `unknown`/NULL and declares `observable_steps` so the console
reports the journey funnel as unmeasurable from this source and uses simulated
sessions for it instead, clearly labelled.

22.8% of lines have no customer id. Those are kept as anonymous rows with
`user_id = NULL` and `is_new_user = NULL` rather than dropped, so revenue totals
still reconcile against the source file; the RFM models simply exclude them.
"""

from __future__ import annotations

import re
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

import pandas as pd

from cartiq_api.datasets.base import DatasetMeta, IngestResult

ONLINE_RETAIL_II = DatasetMeta(
    key="online-retail-ii",
    name="Online Retail II (UCI Machine Learning Repository)",
    url="https://archive.ics.uci.edu/dataset/502/online+retail+ii",
    licence="CC BY 4.0",
    attribution=(
        "Chen, D. (2019). Online Retail II [Dataset]. UCI Machine Learning Repository. "
        "https://doi.org/10.24432/C5CG6D. Licensed CC BY 4.0."
    ),
    # Only the purchase step is directly observable; everything above it in the
    # funnel requires behavioural events this dataset does not contain.
    observable_steps=("visit", "purchase"),
    auto_downloadable=True,
)

DOWNLOAD_URL = "https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip"
ARCHIVE_NAME = "online_retail_II.zip"
WORKBOOK_NAME = "online_retail_II.xlsx"
SHEETS = ("Year 2009-2010", "Year 2010-2011")

#: Stock codes that are charges or adjustments, not catalog products. Taken
#: from the 63 non-standard codes in the file; a real product code is five
#: digits with an optional one or two letter suffix.
NON_PRODUCT_CODES = frozenset(
    {
        "POST",
        "DOT",
        "M",
        "m",
        "C2",
        "C3",
        "D",
        "S",
        "B",
        "PADS",
        "BANK CHARGES",
        "ADJUST",
        "ADJUST2",
        "AMAZONFEE",
        "CRUK",
        "TEST001",
        "TEST002",
        "gift_0001_10",
        "gift_0001_20",
        "gift_0001_30",
        "gift_0001_40",
        "gift_0001_50",
        "SP1002",
    }
)

PRODUCT_CODE_RE = re.compile(r"^\d{4,6}[A-Za-z]{0,3}$")


def is_product_code(code: str) -> bool:
    """True when a stock code denotes a catalog product rather than a charge."""
    if code in NON_PRODUCT_CODES:
        return False
    return bool(PRODUCT_CODE_RE.match(code))


def download(dest_dir: Path) -> Path:
    """Fetch and extract the workbook if it is not already present.

    No credentials needed, which is why this is the default source: `make ingest`
    produces real data on a clean checkout.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    workbook = dest_dir / WORKBOOK_NAME
    if workbook.exists():
        return workbook

    archive = dest_dir / ARCHIVE_NAME
    if not archive.exists():
        # Fixed, hard-coded HTTPS URL for a public dataset; no user input.
        with urllib.request.urlopen(DOWNLOAD_URL, timeout=300) as response:
            archive.write_bytes(response.read())

    with zipfile.ZipFile(archive) as zf:
        # Guard against path traversal in the archive.
        for member in zf.namelist():
            if Path(member).name != member:
                raise ValueError(f"unexpected path in archive: {member}")
        zf.extractall(dest_dir)
    return workbook


def load_raw(path: Path, limit: int | None = None) -> pd.DataFrame:
    """Read both sheets of the workbook into one frame.

    Parsing 1.07M rows of xlsx takes roughly a minute, so the result is cached
    next to the source as Parquet and reused on later runs.
    """
    cache = path.with_suffix(".parquet")
    if cache.exists():
        frame = pd.read_parquet(cache)
    else:
        frames = [pd.read_excel(path, sheet_name=sheet, engine="openpyxl") for sheet in SHEETS]
        frame = pd.concat(frames, ignore_index=True)
        frame.columns = [str(c).strip() for c in frame.columns]
        # Invoice and StockCode hold a mix of ints and strings across the two
        # sheets ("489434" and "C489449"), which Parquet will not accept.
        for column in ("Invoice", "StockCode", "Description", "Country"):
            frame[column] = frame[column].astype("string")
        frame.to_parquet(cache, index=False)
    return frame.head(limit) if limit else frame


def clean(raw: pd.DataFrame) -> IngestResult:
    """Clean the raw frame into events, products and returns.

    Every dropped row is counted under a named reason so the import reconciles
    against the source file exactly.
    """
    rows_read = len(raw)
    dropped: dict[str, int] = {}

    frame = raw.rename(
        columns={
            "Invoice": "invoice",
            "StockCode": "stock_code",
            "Description": "description",
            "Quantity": "quantity",
            "InvoiceDate": "invoice_date",
            "Price": "price",
            "Customer ID": "customer_id",
            "Country": "country",
        }
    ).copy()

    frame["invoice"] = frame["invoice"].astype(str).str.strip()
    frame["stock_code"] = frame["stock_code"].astype(str).str.strip()
    frame["description"] = frame["description"].astype("string").str.strip()
    frame["invoice_date"] = pd.to_datetime(frame["invoice_date"], utc=True)

    # A leading "C" marks a cancellation; those rows carry negative quantities.
    is_cancellation = frame["invoice"].str.upper().str.startswith("C")
    returns_frame = frame[is_cancellation].copy()
    frame = frame[~is_cancellation]

    # Charges and adjustments are not catalog products and must not become
    # product events, but their value still belongs to the order.
    # astype(bool) matters: .map over an EMPTY series yields float64, and
    # indexing a frame with a non-boolean series selects columns instead of
    # rows, which silently destroys the frame.
    product_mask = frame["stock_code"].map(is_product_code).astype(bool)
    charges = frame[~product_mask]
    dropped["non_product_code"] = int(len(charges))
    frame = frame[product_mask]

    bad_quantity = frame["quantity"] <= 0
    dropped["non_positive_quantity"] = int(bad_quantity.sum())
    frame = frame[~bad_quantity]

    bad_price = frame["price"] <= 0
    dropped["non_positive_price"] = int(bad_price.sum())
    frame = frame[~bad_price]

    events = _build_events(frame)
    products = _build_products(frame)
    returns = _build_returns(returns_frame)

    return IngestResult(
        events=events,
        products=products,
        returns=returns,
        rows_read=rows_read,
        dropped=dropped,
    )


def _user_id(customer_id: Any) -> str | None:
    """Stable pseudonymous id, or None when the line is unattributed."""
    if pd.isna(customer_id):
        return None
    return f"cust_{int(float(str(customer_id)))}"


def _build_events(lines: pd.DataFrame) -> pd.DataFrame:
    """Turn invoice lines into purchase events, one per line, plus a visit.

    One invoice is treated as one session: it is the only session boundary the
    source actually provides, and that mapping is documented rather than
    silently assumed.
    """
    if lines.empty:
        return pd.DataFrame(
            columns=[
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
                "properties",
                "source_row_count",
            ]
        )

    frame = lines.copy()
    frame["user_id"] = frame["customer_id"].map(_user_id)
    frame["session_id"] = "inv_" + frame["invoice"]

    # Lines on a customer's earliest invoice are their first purchase.
    # Unattributed lines stay NULL: the source genuinely cannot say.
    first_invoice_at = frame.groupby("user_id", dropna=True)["invoice_date"].transform("min")
    frame["is_new_user"] = (
        (frame["invoice_date"] == first_invoice_at)
        .astype("boolean")
        # pandas-stubs does not model NAType as a valid `other`, though it is
        # exactly what a nullable boolean column needs here.
        .where(frame["user_id"].notna(), other=pd.NA)  # type: ignore[call-overload]
    )

    purchases = pd.DataFrame(
        {
            "event_type": "purchase",
            "timestamp": frame["invoice_date"],
            "user_id": frame["user_id"],
            "session_id": frame["session_id"],
            # Not observable in this source; never guessed.
            "device": "unknown",
            "traffic_source": "unknown",
            "is_new_user": frame["is_new_user"],
            "page": pd.Series(pd.NA, index=frame.index, dtype="string"),
            "product_id": frame["stock_code"].astype("string"),
            "price": frame["price"].round(2).astype("Float64"),
            "quantity": frame["quantity"].astype("Int64"),
            "properties": [
                {"order_id": invoice, "country": country}
                for invoice, country in zip(frame["invoice"], frame["country"], strict=True)
            ],
            "source_row_count": 1,
        }
    )

    # One synthetic session_start per invoice, so session-grained metrics have a
    # denominator. It is derived, not read from the file, and accounts for no
    # source row.
    sessions = (
        frame.groupby("session_id")
        .agg(
            timestamp=("invoice_date", "min"),
            user_id=("user_id", "first"),
            is_new_user=("is_new_user", "first"),
            country=("country", "first"),
            invoice=("invoice", "first"),
        )
        .reset_index()
    )
    starts = pd.DataFrame(
        {
            "event_type": "session_start",
            "timestamp": sessions["timestamp"],
            "user_id": sessions["user_id"],
            "session_id": sessions["session_id"],
            "device": "unknown",
            "traffic_source": "unknown",
            "is_new_user": sessions["is_new_user"],
            # Typed explicitly: an untyped all-null column changes the dtype of
            # the concatenated frame.
            "page": pd.Series(pd.NA, index=sessions.index, dtype="string"),
            "product_id": pd.Series(pd.NA, index=sessions.index, dtype="string"),
            "price": pd.Series(pd.NA, index=sessions.index, dtype="Float64"),
            "quantity": pd.Series(pd.NA, index=sessions.index, dtype="Int64"),
            "properties": [
                {"order_id": invoice, "country": country, "derived": True}
                for invoice, country in zip(sessions["invoice"], sessions["country"], strict=True)
            ],
            "source_row_count": 0,
        }
    )

    events = pd.concat([starts, purchases], ignore_index=True)
    return events.sort_values(["timestamp", "session_id"]).reset_index(drop=True)


def _build_products(lines: pd.DataFrame) -> pd.DataFrame:
    """Derive the catalog: one row per stock code.

    Title and price are real. Category, attributes and anything else absent from
    the source is derived by `cartiq_api.catalog` and flagged `generated`, which
    is also what makes the Module 6 readiness score honest: most of these
    products genuinely have no brand, GTIN or image.
    """
    if lines.empty:
        return pd.DataFrame(columns=["product_id", "title", "price", "units_sold", "orders"])

    def modal_description(series: pd.Series) -> str | None:
        values = series.dropna()
        if values.empty:
            return None
        return str(values.mode().iloc[0])

    grouped = lines.groupby("stock_code").agg(
        title=("description", modal_description),
        price=("price", "median"),
        units_sold=("quantity", "sum"),
        orders=("invoice", "nunique"),
        first_sold_at=("invoice_date", "min"),
        last_sold_at=("invoice_date", "max"),
    )
    products = grouped.reset_index().rename(columns={"stock_code": "product_id"})
    products["price"] = products["price"].round(2)
    return products


def _build_returns(cancellations: pd.DataFrame) -> pd.DataFrame:
    """Cancellation lines, as positive return quantities."""
    if cancellations.empty:
        return pd.DataFrame(
            columns=["order_id", "user_id", "product_id", "quantity", "unit_price", "occurred_at"]
        )
    frame = cancellations.copy()
    return pd.DataFrame(
        {
            "order_id": frame["invoice"],
            "user_id": frame["customer_id"].map(_user_id),
            "product_id": frame["stock_code"].where(frame["stock_code"].map(is_product_code)),
            "quantity": frame["quantity"].abs().astype(int),
            "unit_price": frame["price"].abs().round(2),
            "occurred_at": frame["invoice_date"],
        }
    ).reset_index(drop=True)
