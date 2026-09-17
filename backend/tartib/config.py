"""Settings, read once from the environment."""

from __future__ import annotations

import hashlib
import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import time
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
    ai_fallback_command: str | None  # e.g. "claude"; unset disables the fallback
    ai_fallback_model: str | None
    autofile_confidence: float
    vapid_public: str | None
    vapid_private: str | None
    vapid_email: str
    summary_time: str  # "HH:MM" in `tz`; the daily digest goes out at the first tick past it

    @property
    def push_enabled(self) -> bool:
        """Without both keys there is nothing to sign with, so the reminder loop stays off."""
        return bool(self.vapid_public and self.vapid_private)

    @property
    def summary_at(self) -> time:
        return parse_hhmm(self.summary_time)

    @property
    def ai_enabled(self) -> bool:
        return self.ai_command.strip().lower() not in ("", "off", "none", "false", "0")

    def codex(self):  # -> CodexConfig; imported lazily to keep config dependency-free
        from tartib.codex import CodexConfig

        return CodexConfig(
            command=self.ai_command,
            model=self.ai_model,
            timeout=self.ai_timeout,
            fallback_command=self.ai_fallback_command,
            fallback_model=self.ai_fallback_model,
        )

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.tz)


def parse_hhmm(value: str) -> time:
    try:
        hour, minute = (int(part) for part in value.strip().split(":", 1))
        return time(hour, minute)
    except ValueError as e:
        raise RuntimeError(f"TARTIB_SUMMARY_TIME must be HH:MM, got {value!r}") from e


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    env = os.environ if env is None else env
    password = env.get("TARTIB_PASSWORD", "")
    if not password:
        raise RuntimeError("TARTIB_PASSWORD is required")
    secret = env.get("TARTIB_SECRET") or hashlib.sha256(f"tartib:{password}".encode()).hexdigest()
    tz = env.get("TARTIB_TZ") or "UTC"
    ZoneInfo(tz)  # fail fast on an unknown zone
    summary_time = (env.get("TARTIB_SUMMARY_TIME") or "08:00").strip()
    parse_hhmm(summary_time)  # fail fast on a bad time
    spaces = tuple(
        dict.fromkeys(
            s.strip().lower() for s in env.get("TARTIB_SPACES", "").split(",") if s.strip()
        )
    )
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
        ai_fallback_command=env.get("TARTIB_AI_FALLBACK_COMMAND") or None,
        ai_fallback_model=env.get("TARTIB_AI_FALLBACK_MODEL") or None,
        autofile_confidence=float(env.get("TARTIB_AUTOFILE_CONFIDENCE") or "0.85"),
        vapid_public=env.get("TARTIB_VAPID_PUBLIC") or None,
        vapid_private=env.get("TARTIB_VAPID_PRIVATE") or None,
        vapid_email=env.get("TARTIB_VAPID_EMAIL") or "mailto:tartib@localhost",
        summary_time=summary_time,
    )
