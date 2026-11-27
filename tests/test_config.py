import pytest

from flight_alert.config import Settings


def test_defaults_match_agreed_search_scope(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "chat")

    settings = Settings.from_env()

    assert settings.origins == ("MXP", "BGY", "LIN")
    assert settings.passengers == 2
    assert settings.min_nights == 2
    assert settings.max_nights == 4
    assert settings.max_total_eur == 100
    assert settings.check_interval_hours == 6
    assert settings.dry_run is False


def test_production_requires_telegram_credentials(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("DRY_RUN", raising=False)

    with pytest.raises(ValueError, match="TELEGRAM_BOT_TOKEN"):
        Settings.from_env()


def test_dry_run_allows_missing_telegram_credentials(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    settings = Settings.from_env()

    assert settings.dry_run is True
    assert settings.telegram_bot_token is None
    assert settings.telegram_chat_id is None


def test_rejects_invalid_night_range(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("MIN_NIGHTS", "1")
    monkeypatch.setenv("MAX_NIGHTS", "4")

    with pytest.raises(ValueError, match="MIN_NIGHTS"):
        Settings.from_env()


def test_rejects_maximum_below_minimum(monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("MIN_NIGHTS", "4")
    monkeypatch.setenv("MAX_NIGHTS", "2")

    with pytest.raises(ValueError, match="MAX_NIGHTS"):
        Settings.from_env()
