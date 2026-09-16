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
    spaces: tuple[str, ...]
    ai_command: str  # "codex", a path, or "off"
    ai_model: str | None
    ai_timeout: float
    autofile_confidence: float

    @property
    def ai_enabled(self) -> bool:
        return self.ai_command.strip().lower() not in ("", "off", "none", "false", "0")

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
    spaces = tuple(
        dict.fromkeys(
            s.strip().lower() for s in env.get("TARTIB_SPACES", "").split(",") if s.strip()
        )
    )
    if not spaces:
        raise RuntimeError("TARTIB_SPACES is required, e.g. TARTIB_SPACES=work,home,health")
    return Settings(
        password=password,
        secret=secret,
        tz=tz,
        db_path=env.get("TARTIB_DB_PATH") or "/data/tartib.db",
        static_dir=env.get("TARTIB_STATIC_DIR") or None,
        spaces=spaces,
        ai_command=env.get("TARTIB_AI_COMMAND", "codex"),
        ai_model=env.get("TARTIB_AI_MODEL") or None,
        ai_timeout=float(env.get("TARTIB_AI_TIMEOUT") or "120"),
        autofile_confidence=float(env.get("TARTIB_AUTOFILE_CONFIDENCE") or "0.85"),
    )
