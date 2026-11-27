from datetime import datetime, timedelta, timezone
from decimal import Decimal

from flight_alert.alerts import AlertPolicy, offer_fingerprint
from flight_alert.models import FlightLeg, FlightOffer
from flight_alert.storage import OfferStore


def make_offer(price="80"):
    now = datetime(2027, 1, 10, 8, tzinfo=timezone.utc)
    leg = FlightLeg("BGY", "SKP", now, now.replace(hour=10), "W6", "1", Decimal(price), "small", "https://x", "fixture", now, True)
    return FlightOffer((leg,), 2, 2, Decimal(price), "round_trip", "fixture", now, "https://x")


def test_same_offer_can_alert_again_after_seven_days(tmp_path):
    store = OfferStore(tmp_path / "offers.db")
    store.initialize()
    policy = AlertPolicy()
    offer = make_offer()
    fingerprint = offer_fingerprint(offer)
    first = datetime(2027, 1, 1, tzinfo=timezone.utc)
    store.record(offer, fingerprint, seen_at=first, notified_at=first)
    assert policy.should_send(offer, store, now=first + timedelta(days=1)) is False
    assert policy.should_send(offer, store, now=first + timedelta(days=8)) is True


def test_dry_run_does_not_mark_notification(tmp_path):
    store = OfferStore(tmp_path / "offers.db")
    store.initialize()
    offer = make_offer()
    fingerprint = offer_fingerprint(offer)
    store.record(offer, fingerprint, notified_at=None)
    assert store.last_notified_price(fingerprint) is None


def test_price_drop_is_compared_to_last_notified_price(tmp_path):
    store = OfferStore(tmp_path / "offers.db")
    store.initialize()
    policy = AlertPolicy()
    first = make_offer("80")
    fingerprint = offer_fingerprint(first)
    store.record(first, fingerprint, notified_at=datetime.now(timezone.utc))
    assert policy.should_send(make_offer("70"), store) is True
