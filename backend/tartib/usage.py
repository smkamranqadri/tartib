"""What the AI costs: prices, the sum, and the once-a-day refresh.

Two things this module is careful about.

**The cost is an estimate twice over.** Both CLIs run on a subscription and report no money at
all, and a catalogue price is list price. Nothing here should be shown as a bill (rule 9).

**It must work with the network blocked.** The rates ship in code, so a first run and a failed
fetch both cost correctly. The refresh writes only the pinned model's four numbers -- the
catalogue is over 5MB to read four figures, and none of the rest of it belongs on this disk.
"""

from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from tartib.clock import utcnow

CATALOGUE = "https://models.dev/api.json"
REFRESH_SECONDS = 24 * 60 * 60
FETCH_TIMEOUT = 20


@dataclass(frozen=True)
class Rates:
    """USD per million tokens."""

    input: float
    output: float
    cache_read: float
    cache_write: float
    source: str = "shipped"  # shipped | cached | fetched

    def cost(self, usage) -> float:
        """USD for one call. `billable()` excludes reasoning tokens, which the CLI already
        counts inside `output_tokens` -- pricing both would bill reasoning twice, and on a
        reasoning model that is most of the bill."""
        fresh, cached, written, output = usage.billable()
        return (
            fresh * self.input
            + cached * self.cache_read
            + written * self.cache_write
            + output * self.output
        ) / 1_000_000


# gpt-5.6-luna, read from the catalogue on 2026-09-22. Shipped so the app never depends on the
# network to put a number on a call; the refresh keeps them current when it can.
SHIPPED = {
    "gpt-5.6-luna": Rates(input=0.20, output=1.20, cache_read=0.02, cache_write=0.25),
}
UNKNOWN = Rates(input=0.0, output=0.0, cache_read=0.0, cache_write=0.0, source="unknown")


def _cache_path(db_path: str) -> Path:
    return Path(db_path).parent / "ai-prices.json"


def _read_cache(db_path: str, model: str) -> Rates | None:
    try:
        blob = json.loads(_cache_path(db_path).read_text())
    except (OSError, ValueError):
        return None
    entry = blob.get(model)
    if not isinstance(entry, dict):
        return None
    try:
        return Rates(
            input=float(entry["input"]),
            output=float(entry["output"]),
            cache_read=float(entry["cache_read"]),
            cache_write=float(entry["cache_write"]),
            source="cached",
        )
    except (KeyError, TypeError, ValueError):
        return None


def rates_for(model: str | None, db_path: str) -> Rates:
    """The best rates available, without ever going to the network. Cached, then shipped."""
    if not model:
        return UNKNOWN
    return _read_cache(db_path, model) or SHIPPED.get(model) or UNKNOWN


def _stale(db_path: str) -> bool:
    """Whether a refresh is due. Measured from the last *attempt*, not the last success.

    It used to read the cache file's mtime, which only a successful fetch wrote. So an
    unlisted model or an unreachable network meant every single `/api/usage` downloaded the
    whole catalogue again -- and offline, blocked for the full timeout each time, on every page
    load. "At most once a day" was only true when it worked.
    """
    path = _cache_path(db_path)
    try:
        age = utcnow().timestamp() - path.stat().st_mtime
    except OSError:
        return True
    return age > REFRESH_SECONDS


def _mark_attempt(db_path: str) -> None:
    """Touch the cache so a failed fetch also waits a day before trying again. Creates the file
    if it is not there yet, so a first attempt that fails does not retry on every request."""
    path = _cache_path(db_path)
    try:
        if not path.exists():
            path.write_text("{}")
        else:
            path.touch()
    except OSError:
        pass


def refresh(model: str | None, db_path: str) -> Rates | None:
    """Fetch the catalogue and keep only this model's four numbers. Returns the new rates, or
    None when nothing was written -- too soon, unreachable, or the model is not listed.

    A failure leaves the last good copy exactly where it was: an unreachable price server must
    never turn a working cost into a blank one.
    """
    if not model or not _stale(db_path):
        return None
    # Recorded before the attempt, so every path out of here -- unreachable, unlisted model,
    # malformed block -- waits a day before the next one.
    _mark_attempt(db_path)
    try:
        with urllib.request.urlopen(CATALOGUE, timeout=FETCH_TIMEOUT) as response:  # noqa: S310
            catalogue = json.loads(response.read().decode())
    except Exception:  # noqa: BLE001 -- any failure means "keep what we have"
        return None
    for provider in catalogue.values():
        if not isinstance(provider, dict):
            continue
        entry = (provider.get("models") or {}).get(model)
        cost = (entry or {}).get("cost") if isinstance(entry, dict) else None
        if not isinstance(cost, dict):
            continue
        try:
            found = {
                "input": float(cost["input"]),
                "output": float(cost["output"]),
                "cache_read": float(cost.get("cache_read", 0.0)),
                "cache_write": float(cost.get("cache_write", 0.0)),
            }
        except (KeyError, TypeError, ValueError):
            return None
        try:
            path = _cache_path(db_path)
            blob = {}
            if path.exists():
                try:
                    blob = json.loads(path.read_text())
                except ValueError:
                    blob = {}
            blob[model] = found
            path.write_text(json.dumps(blob))
        except OSError:
            return None
        return Rates(**found, source="fetched")
    return None
