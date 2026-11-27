from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class Settings:
    origins: tuple[str, ...]
    passengers: int
    min_nights: int
    max_nights: int
    max_total_eur: int
    search_until: date
    check_interval_hours: int
    telegram_bot_token: str | None
    telegram_chat_id: str | None
    dry_run: bool
    provider_urls: tuple[str, ...]
    provider: str
    state_db: Path
    max_routes: int

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        env = os.environ if environ is None else environ
        dry_run = _boolean(env.get("DRY_RUN", "false"))
        token = _optional(env.get("TELEGRAM_BOT_TOKEN"))
        chat_id = _optional(env.get("TELEGRAM_CHAT_ID"))
        if not dry_run and not token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required unless DRY_RUN=true")
        if not dry_run and not chat_id:
            raise ValueError("TELEGRAM_CHAT_ID is required unless DRY_RUN=true")

        origins = _csv(env.get("ORIGINS", "MXP,BGY,LIN"))
        if not origins:
            raise ValueError("ORIGINS must contain at least one airport")
        min_nights = _integer(env.get("MIN_NIGHTS", "2"), "MIN_NIGHTS")
        max_nights = _integer(env.get("MAX_NIGHTS", "4"), "MAX_NIGHTS")
        if min_nights < 2:
            raise ValueError("MIN_NIGHTS must be at least 2")
        if max_nights < min_nights:
            raise ValueError("MAX_NIGHTS must be greater than or equal to MIN_NIGHTS")

        return cls(
            origins=origins,
            passengers=_positive_integer(env.get("PASSENGERS", "2"), "PASSENGERS"),
            min_nights=min_nights,
            max_nights=max_nights,
            max_total_eur=_positive_integer(env.get("MAX_TOTAL_EUR", "100"), "MAX_TOTAL_EUR"),
            search_until=date.fromisoformat(env.get("SEARCH_UNTIL", "2027-03-31")),
            check_interval_hours=_positive_integer(
                env.get("CHECK_INTERVAL_HOURS", "6"), "CHECK_INTERVAL_HOURS"
            ),
            telegram_bot_token=token,
            telegram_chat_id=chat_id,
            dry_run=dry_run,
            provider_urls=_urls(env.get("PROVIDER_URLS", "")),
            provider=env.get("PROVIDER", "ryanair").strip().lower(),
            state_db=Path(env.get("STATE_DB", "offers.db")),
            max_routes=_positive_integer(env.get("MAX_ROUTES", "100"), "MAX_ROUTES"),
        )


def _optional(value: str | None) -> str | None:
    value = value.strip() if value else ""
    return value or None


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip().upper() for item in value.split(",") if item.strip())


def _urls(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _integer(value: str, name: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _positive_integer(value: str, name: str) -> int:
    parsed = _integer(value, name)
    if parsed <= 0:
        raise ValueError(f"{name} must be positive")
    return parsed


def _boolean(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError("DRY_RUN must be a boolean")
