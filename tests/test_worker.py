from datetime import datetime, timezone
from decimal import Decimal

import pytest

from flight_alert.config import Settings
from flight_alert.models import FlightLeg, FlightOffer
from flight_alert.search import SearchReport
from flight_alert.worker import build_provider, run_once


def test_dry_run_worker_does_not_send_telegram(tmp_path, monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("PROVIDER_URLS", "")
    settings = Settings.from_env()
    report = run_once(settings, store_path=tmp_path / "offers.db")
    assert isinstance(report, SearchReport)


def test_invalid_configuration_is_not_hidden(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "false")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        Settings.from_env()


def test_unknown_provider_url_is_rejected():
    settings = Settings.from_env({"DRY_RUN": "true", "PROVIDER": "bogus-provider"})
    with pytest.raises(ValueError, match="provider"):
        build_provider(settings)
