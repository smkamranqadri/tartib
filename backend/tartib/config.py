"""Settings, read once from the environment."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from dataclasses import dataclass
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Settings:
    password: str
    secret: str
    tz: str
    db_path: str
    static_dir: str | None
    ai_base_url: str | None
    ai_api_key: str | None
    ai_model: str | None
    autofile_confidence: float

    @property
    def ai_enabled(self) -> bool:
        return bool(self.ai_base_url and self.ai_model)

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.tz)


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env
    password = env.get("TARTIB_PASSWORD", "")
    if not password:
        raise RuntimeError("TARTIB_PASSWORD is required")
    secret = env.get("TARTIB_SECRET") or hashlib.sha256(f"tartib:{password}".encode()).hexdigest()
    tz = env.get("TARTIB_TZ") or "UTC"
    ZoneInfo(tz)  # fail fast on an unknown zone
    return Settings(
        password=password,
        secret=secret,
        tz=tz,
        db_path=env.get("TARTIB_DB_PATH") or "/data/tartib.db",
        static_dir=env.get("TARTIB_STATIC_DIR") or None,
        ai_base_url=(env.get("TARTIB_AI_BASE_URL") or "").rstrip("/") or None,
        ai_api_key=env.get("TARTIB_AI_API_KEY") or None,
        ai_model=env.get("TARTIB_AI_MODEL") or None,
        autofile_confidence=float(env.get("TARTIB_AUTOFILE_CONFIDENCE") or "0.85"),
    )
