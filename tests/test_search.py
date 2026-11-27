from datetime import datetime, timezone
from decimal import Decimal

from flight_alert.config import Settings
from flight_alert.models import FlightLeg, FlightOffer
from flight_alert.search import SearchEngine, combine_one_way


def leg(origin, destination, day, hour, price, url):
    departure = datetime(2027, 1, day, hour, tzinfo=timezone.utc)
    return FlightLeg(
        origin=origin,
        destination=destination,
        departure=departure,
        arrival=departure.replace(hour=hour + 2),
        carrier="W6",
        flight_number="100",
        mandatory_total_eur=Decimal(price),
        optional_baggage_note="small bag",
        booking_url=url,
        source="fixture",
        retrieved_at=datetime(2026, 11, 27, tzinfo=timezone.utc),
        verified=True,
    )


def one_way(origin, destination, day, price, url):
    flight_leg = leg(origin, destination, day, 8, price, url)
    return FlightOffer(
        legs=(flight_leg,),
        nights=1,
        passengers=2,
        total_mandatory_eur=Decimal(price),
        offer_type="separate_one_way",
        source="fixture",
        retrieved_at=flight_leg.retrieved_at,
        booking_url=url,
    )


def test_combines_only_compatible_two_to_four_night_one_way_tickets():
    offers = combine_one_way(
        [one_way("BGY", "SKP", 10, "30", "out")],
        [one_way("SKP", "BGY", 13, "40", "back")],
        2,
        4,
    )

    assert len(offers) == 1
    assert offers[0].nights == 3
    assert offers[0].total_mandatory_eur == Decimal("70.00")
    assert offers[0].booking_url == "out\nback"


def test_discards_incompatible_one_way_tickets():
    result = combine_one_way(
        [one_way("BGY", "SKP", 10, "30", "out")],
        [one_way("ATH", "BGY", 13, "40", "wrong-airport")],
        2,
        4,
    )
    assert result == []


class FixtureProvider:
    name = "fixture"

    def destinations(self, origins):
        return ["SKP", "ATH"]

    def search(self, origin, destination, start_date, end_date, nights, passengers):
        if destination == "SKP" and origin == "BGY" and nights == 2:
            return [
                FlightOffer(
                    legs=(leg("BGY", "SKP", 10, 8, "45", "rt"), leg("SKP", "BGY", 12, 10, "45", "rt")),
                    nights=2,
                    passengers=2,
                    total_mandatory_eur=Decimal("90"),
                    offer_type="round_trip",
                    source=self.name,
                    retrieved_at=datetime(2026, 11, 27, tzinfo=timezone.utc),
                    booking_url="rt",
                )
            ]
        if destination == "SKP" and origin == "BGY":
            return [one_way("BGY", "SKP", 10, "30", "out")]
        if destination == "SKP" and origin == "SKP":
            return [one_way("SKP", "BGY", 12, "30", "back")]
        return []


def test_search_engine_checks_origins_nights_and_budget():
    settings = Settings.from_env({"DRY_RUN": "true", "SEARCH_UNTIL": "2027-03-31"})
    report = SearchEngine(FixtureProvider(), settings).run_cycle()

    assert report.destinations_checked == 2
    assert report.queries_completed > 0
    assert all(offer.total_mandatory_eur <= Decimal("100") for offer in report.offers)
    assert any(offer.offer_type == "round_trip" for offer in report.offers)
