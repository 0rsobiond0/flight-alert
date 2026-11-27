from datetime import datetime, timezone
from decimal import Decimal

from flight_alert.models import FlightLeg, FlightOffer
from flight_alert.search import filter_round_trip_offers


def make_offer(kind, nights, passengers=2):
    now = datetime(2027, 1, 10, 8, tzinfo=timezone.utc)
    outbound = FlightLeg("BGY", "SKP", now, now.replace(hour=10), "W6", "1", Decimal("30"), "small", "https://out", "fixture", now, True)
    inbound = FlightLeg("SKP", "BGY", now.replace(day=10 + nights), now.replace(day=10 + nights, hour=12), "W6", "2", Decimal("30"), "small", "https://in", "fixture", now, True)
    legs = (outbound, inbound) if kind == "round_trip" else (outbound,)
    return FlightOffer(legs, nights, passengers, Decimal("60"), kind, "fixture", now, "https://x")


def test_only_exact_round_trip_matches_requested_nights_and_passengers():
    result = filter_round_trip_offers(
        [make_offer("round_trip", 2), make_offer("round_trip", 3), make_offer("separate_one_way", 2), make_offer("round_trip", 2, 1)],
        requested_nights=2,
        passengers=2,
    )
    assert len(result) == 1
    assert result[0].offer_type == "round_trip"
    assert result[0].nights == 2
