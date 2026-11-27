from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import httpx

from flight_alert.alerts import AlertPolicy, format_offer
from flight_alert.config import Settings
from flight_alert.providers.ryanair_api import RyanairApiProvider
from flight_alert.search import SearchEngine, SearchReport
from flight_alert.storage import OfferStore, offer_fingerprint
from flight_alert.telegram import TelegramClient

LOGGER = logging.getLogger("flight_alert")


def build_provider(settings: Settings) -> RyanairApiProvider:
    if settings.provider not in ("ryanair", "ryanair-api"):
        raise ValueError(f"unsupported provider: {settings.provider!r}")
    offline = settings.dry_run and not settings.provider_urls
    return RyanairApiProvider(httpx.Client(), max_routes=settings.max_routes, offline=offline)


def run_once(settings: Settings, store_path: Path | None = None) -> SearchReport:
    provider = build_provider(settings)
    store = OfferStore(store_path or settings.state_db)
    store.initialize()
    report = SearchEngine(provider, settings).run_cycle()
    policy = AlertPolicy()
    with httpx.Client() as http_client:
        telegram = TelegramClient(settings.telegram_bot_token, settings.telegram_chat_id, http_client)
        for offer in report.offers:
            fingerprint = offer_fingerprint(offer)
            should_send = policy.should_send(offer, store)
            if should_send:
                telegram.send(format_offer(offer), dry_run=settings.dry_run)
            store.record(
                offer,
                fingerprint,
                notified_at=None if settings.dry_run or not should_send else datetime.now(timezone.utc),
            )
    LOGGER.info(json.dumps({
        "event": "search_cycle",
        "destinations_checked": report.destinations_checked,
        "queries_completed": report.queries_completed,
        "queries_skipped": report.queries_skipped,
        "offers": len(report.offers),
        "provider_errors": len(report.provider_errors),
    }))
    return report
