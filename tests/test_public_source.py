from datetime import date
from decimal import Decimal

import pytest

from flight_alert.providers.public_source import PublicSourceProvider, parse_public_payload


PAYLOAD = {
    "destinations": ["SKP", "ATH"],
    "offers": [
        {
            "origin": "BGY",
            "destination": "SKP",
            "departure": "2027-01-10T08:00:00+00:00",
            "arrival": "2027-01-10T10:00:00+00:00",
            "carrier": "W6",
            "flight_number": "4774",
            "price": "24.99",
            "currency": "EUR",
            "per_person": True,
            "mandatory_fees": "0",
            "booking_url": "https://example.test/out",
            "verified": True,
        }
    ],
}


def test_parses_structured_public_payload():
    provider = PublicSourceProvider.from_payload(PAYLOAD, source_name="fixture")
    assert provider.destinations(("BGY",)) == ["SKP", "ATH"]
    offers = provider.search("BGY", "SKP", date(2027, 1, 1), date(2027, 3, 31), 1, 2)
    assert offers[0].total_mandatory_eur == Decimal("49.98")
    assert offers[0].legs[0].verified is True


def test_rejects_missing_price_instead_of_treating_it_as_free():
    broken = {"destinations": [], "offers": [{"origin": "BGY", "destination": "SKP"}]}
    with pytest.raises(ValueError, match="price"):
        parse_public_payload(broken, source_name="fixture")


def test_rejects_malformed_payload():
    with pytest.raises(ValueError, match="offers"):
        parse_public_payload({"destinations": ["SKP"]}, source_name="fixture")
