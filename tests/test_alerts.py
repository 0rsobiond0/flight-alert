from datetime import datetime, timezone
from decimal import Decimal

from flight_alert.alerts import AlertPolicy, format_offer, offer_fingerprint
from flight_alert.models import FlightLeg, FlightOffer
from flight_alert.storage import OfferStore
from flight_alert.telegram import TelegramClient


def offer(price="80"):
    now = datetime(2026, 11, 27, tzinfo=timezone.utc)
    leg = FlightLeg("BGY", "SKP", datetime(2027, 1, 10, 8, tzinfo=timezone.utc), datetime(2027, 1, 10, 10, tzinfo=timezone.utc), "W6", "1", Decimal(price), "small bag", "https://x", "fixture", now, True)
    return FlightOffer((leg,), 2, 2, Decimal(price), "round_trip", "fixture", now, "https://x")


def test_format_includes_total_nights_source_and_link():
    text = format_offer(offer())
    assert "80.00 EUR" in text
    assert "2 notti" in text
    assert "BGY → SKP" in text
    assert "https://x" in text


def test_policy_realerts_after_ten_euro_drop(tmp_path):
    store = OfferStore(tmp_path / "offers.db")
    store.initialize()
    policy = AlertPolicy()
    first = offer("80")
    fingerprint = offer_fingerprint(first)
    assert policy.should_send(first, store) is True
    store.record(first, fingerprint)
    assert policy.should_send(offer("75"), store) is False
    assert policy.should_send(offer("70"), store) is True


def test_telegram_dry_run_does_not_require_network():
    client = TelegramClient(None, None, None)
    assert client.send("hello", dry_run=True) is None
