from datetime import datetime, timedelta, timezone
from decimal import Decimal

from flight_alert.models import FlightLeg, FlightOffer
from flight_alert.storage import OfferStore, offer_fingerprint


def make_offer(price="80"):
    now = datetime(2026, 11, 27, tzinfo=timezone.utc)
    leg = FlightLeg(
        origin="BGY", destination="SKP", departure=datetime(2027, 1, 10, 8, tzinfo=timezone.utc),
        arrival=datetime(2027, 1, 10, 10, tzinfo=timezone.utc), carrier="W6", flight_number="1",
        mandatory_total_eur=Decimal(price), optional_baggage_note="small bag", booking_url="https://x",
        source="fixture", retrieved_at=now, verified=True,
    )
    return FlightOffer((leg,), 2, 2, Decimal(price), "round_trip", "fixture", now, "https://x")


def test_store_initializes_and_suppresses_recent_duplicate(tmp_path):
    store = OfferStore(tmp_path / "offers.db")
    store.initialize()
    offer = make_offer()
    fingerprint = offer_fingerprint(offer)
    now = datetime.now(timezone.utc)

    assert store.seen_recently(fingerprint, now) is False
    store.record(offer, fingerprint)
    assert store.seen_recently(fingerprint, now) is True
    assert store.last_price(fingerprint) == Decimal("80.00")


def test_old_duplicate_is_not_recent(tmp_path):
    store = OfferStore(tmp_path / "offers.db")
    store.initialize()
    offer = make_offer()
    fingerprint = offer_fingerprint(offer)
    store.record(offer, fingerprint, seen_at=datetime.now(timezone.utc) - timedelta(days=8))
    assert store.seen_recently(fingerprint, datetime.now(timezone.utc)) is False
