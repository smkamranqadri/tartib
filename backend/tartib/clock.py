"""Time helpers. Everything stored is UTC ISO 8601; 'today' is computed in the configured zone."""

from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo


def utcnow() -> datetime:
    return datetime.now(UTC)


def utcnow_iso() -> str:
    return utcnow().replace(microsecond=0).isoformat().replace("+00:00", "Z")


def utcnow_ms_iso() -> str:
    """Millisecond precision, matching what the items touch trigger writes."""
    return utcnow().isoformat(timespec="milliseconds").replace("+00:00", "Z")


def today_in(zone: ZoneInfo, now: datetime | None = None) -> date:
    return (now or utcnow()).astimezone(zone).date()
