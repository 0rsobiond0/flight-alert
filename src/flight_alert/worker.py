from __future__ import annotations

import json
import logging
from pathlib import Path

import httpx

from flight_alert.alerts import AlertPolicy, format_offer
from flight_alert.config import Settings
from flight_alert.providers.public_source import PublicSourceProvider
from flight_alert.search import SearchEngine, SearchReport
from flight_alert.storage import OfferStore, offer_fingerprint
from flight_alert.telegram import TelegramClient

LOGGER = logging.getLogger("flight_alert")


def build_provider(settings: Settings) -> PublicSourceProvider:
    if len(settings.provider_urls) > 1:
        raise ValueError("only one permitted provider URL is supported in the initial release")
    for url in settings.provider_urls:
        if not url.startswith("https://") or "not-allowed" in url:
            raise ValueError(f"provider URL is not permitted: {url}")
    # Live source wiring is deliberately explicit: a source must publish the
    # structured payload contract before it can be enabled in production.
    return PublicSourceProvider(source_name="configured-public-source")


def run_once(settings: Settings, store_path: Path = Path("offers.db")) -> SearchReport:
    provider = build_provider(settings)
    store = OfferStore(store_path)
    store.initialize()
    report = SearchEngine(provider, settings).run_cycle()
    policy = AlertPolicy()
    with httpx.Client() as http_client:
        telegram = TelegramClient(settings.telegram_bot_token, settings.telegram_chat_id, http_client)
        for offer in report.offers:
            fingerprint = offer_fingerprint(offer)
            if policy.should_send(offer, store):
                telegram.send(format_offer(offer), dry_run=settings.dry_run)
            store.record(offer, fingerprint)
    LOGGER.info(
        json.dumps(
            {
                "event": "search_cycle",
                "destinations_checked": report.destinations_checked,
                "queries_completed": report.queries_completed,
                "queries_skipped": report.queries_skipped,
                "offers": len(report.offers),
                "provider_errors": len(report.provider_errors),
            }
        )
    )
    return report
