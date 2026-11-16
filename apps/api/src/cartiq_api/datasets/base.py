"""Shared types for dataset loaders."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class DatasetMeta:
    """Everything needed to attribute and reproduce a dataset import."""

    key: str
    name: str
    url: str
    licence: str
    attribution: str
    #: Funnel step keys this source can actually observe. The console reads this
    #: instead of assuming every step is measurable everywhere.
    observable_steps: tuple[str, ...]
    #: True when the file can be fetched without credentials.
    auto_downloadable: bool
    #: Shown when the file must be fetched by hand.
    manual_download_note: str = ""


@dataclass
class IngestResult:
    """Cleaned output of a dataset loader.

    Attributes:
        events: Rows ready for the `events` table.
        products: Rows ready for the `products` table.
        returns: Rows ready for the `return_lines` table.
        rows_read: Rows in the source file before cleaning.
        dropped: {reason: count} for every row removed, so the import reconciles.
    """

    events: pd.DataFrame
    products: pd.DataFrame
    returns: pd.DataFrame
    rows_read: int
    dropped: dict[str, int] = field(default_factory=dict)

    @property
    def rows_loaded(self) -> int:
        """Number of event rows that survived cleaning."""
        return len(self.events)

    def reconciles(self) -> bool:
        """True when every source row is either loaded, returned or explained.

        One source line can produce more than one event (an invoice also emits a
        `session_start`), so the check is on accounted-for source rows, not on
        event count.
        """
        accounted = (
            int(self.events["source_row_count"].sum())
            if "source_row_count" in self.events
            else self.rows_loaded
        )
        return accounted + len(self.returns) + sum(self.dropped.values()) == self.rows_read


def sha256_of(path: Path, chunk_size: int = 1 << 20) -> str:
    """SHA-256 of a file, so an import is tied to exact bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()
