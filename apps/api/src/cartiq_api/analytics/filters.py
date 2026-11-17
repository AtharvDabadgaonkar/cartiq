"""Slice definition shared by every diagnosis query."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

#: Sources that can support a journey funnel. A transactional import records
#: only completed purchases, so its sessions are 100% converted by construction.
FUNNEL_CAPABLE_SOURCES: tuple[str, ...] = ("SIMULATED", "LIVE_DEMO")


@dataclass(frozen=True)
class Filters:
    """A slice of sessions.

    Every field is optional; an unset field means "do not filter on this".
    `data_source` is deliberately required-by-default to `SIMULATED`, because
    mixing real and simulated sessions in one funnel is the single easiest way
    to produce a number that means nothing.
    """

    data_source: str = "SIMULATED"
    date_from: date | None = None
    date_to: date | None = None
    devices: tuple[str, ...] = ()
    traffic_sources: tuple[str, ...] = ()
    segments: tuple[str, ...] = ()
    #: None = both, True = new visitors only, False = returning only.
    is_new_user: bool | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def where(self, alias: str = "") -> tuple[str, dict[str, Any]]:
        """Build a SQL WHERE body and its bound parameters.

        Returns a parameterised fragment — never interpolated values — so a
        filter coming from a URL cannot become an injection.
        """
        prefix = f"{alias}." if alias else ""
        # Cast to text: data_source is a Postgres enum, so an unrecognised
        # value would raise instead of simply matching nothing.
        clauses = [f"{prefix}data_source::text = :data_source"]
        params: dict[str, Any] = {"data_source": self.data_source}

        if self.date_from is not None:
            clauses.append(f"{prefix}session_date >= :date_from")
            params["date_from"] = self.date_from
        if self.date_to is not None:
            clauses.append(f"{prefix}session_date <= :date_to")
            params["date_to"] = self.date_to
        if self.devices:
            clauses.append(f"{prefix}device = ANY(:devices)")
            params["devices"] = list(self.devices)
        if self.traffic_sources:
            clauses.append(f"{prefix}traffic_source = ANY(:traffic_sources)")
            params["traffic_sources"] = list(self.traffic_sources)
        if self.segments:
            clauses.append(f"{prefix}segment = ANY(:segments)")
            params["segments"] = list(self.segments)
        if self.is_new_user is not None:
            clauses.append(f"{prefix}is_new_user IS NOT DISTINCT FROM :is_new_user")
            params["is_new_user"] = self.is_new_user

        return " AND ".join(clauses), params

    @property
    def supports_funnel(self) -> bool:
        """True when this source can express a journey funnel at all."""
        return self.data_source in FUNNEL_CAPABLE_SOURCES

    def describe(self) -> str:
        """One-line human description, for chart captions and readouts."""
        parts = [self.data_source.replace("_", " ").title()]
        if self.date_from or self.date_to:
            parts.append(f"{self.date_from or 'start'} to {self.date_to or 'end'}")
        if self.devices:
            parts.append("device: " + ", ".join(self.devices))
        if self.traffic_sources:
            parts.append("source: " + ", ".join(self.traffic_sources))
        if self.segments:
            parts.append("segment: " + ", ".join(self.segments))
        if self.is_new_user is not None:
            parts.append("new visitors" if self.is_new_user else "returning visitors")
        return " · ".join(parts)
