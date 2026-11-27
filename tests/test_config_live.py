from flight_alert.config import Settings


def test_live_provider_and_state_db_are_configurable():
    settings = Settings.from_env({
        "DRY_RUN": "true",
        "PROVIDER": "ryanair",
        "STATE_DB": "/var/lib/flight-alert/offers.db",
        "PROVIDER_URLS": "https://www.ryanair.com/ie/en/flights/flights-from-bergamo-to-athens",
        "MAX_ROUTES": "12",
    })
    assert settings.provider == "ryanair"
    assert str(settings.state_db) == "/var/lib/flight-alert/offers.db"
    assert settings.provider_urls[0].startswith("https://")
    assert settings.max_routes == 12
