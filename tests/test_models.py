from datetime import datetime, timezone
from decimal import Decimal

import pytest

from flight_alert.models import FlightLeg, FlightOffer


def make_leg(verified=True):
    return FlightLeg(
        origin="BGY",
        destination="SKP",
        departure=datetime(2027, 1, 15, 8, tzinfo=timezone.utc),
        arrival=datetime(2027, 1, 15, 10, tzinfo=timezone.utc),
        carrier="W6",
        flight_number="4774",
        mandatory_total_eur=Decimal("24.99"),
        optional_baggage_note="small personal item only",
        booking_url="https://example.test/flight",
        source="example",
        retrieved_at=datetime(2026, 11, 27, tzinfo=timezone.utc),
        verified=verified,
    )


def test_offer_preserves_unverified_state_and_cost():
    leg = make_leg(verified=False)
    offer = FlightOffer(
        legs=(leg,),
        nights=2,
        passengers=2,
        total_mandatory_eur=Decimal("49.98"),
        offer_type="separate_one_way",
        source="example",
        retrieved_at=leg.retrieved_at,
        booking_url=leg.booking_url,
        verification_note="price requires final checkout verification",
    )

    assert offer.total_mandatory_eur == Decimal("49.98")
    assert offer.verified is False
    assert offer.verification_note is not None


def test_rejects_incomplete_offer_cost():
    leg = make_leg()
    with pytest.raises(ValueError, match="total_mandatory_eur"):
        FlightOffer(
            legs=(leg,),
            nights=2,
            passengers=2,
            total_mandatory_eur=None,
            offer_type="round_trip",
            source="example",
            retrieved_at=leg.retrieved_at,
        )
