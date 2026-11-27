from datetime import date, datetime
from decimal import Decimal

import pytest

from flight_alert.providers.ryanair_api import RyanairApiProvider, parse_farfnd_response

RESPONSE = {
    "fares": [
        {
            "outbound": {
                "departureAirport": {"iataCode": "BGY"},
                "arrivalAirport": {"iataCode": "ATH"},
                "departureDate": "2027-01-18T07:35:00",
                "arrivalDate": "2027-01-18T11:00:00",
                "price": {"value": 43.98, "currencyCode": "EUR"},
                "flightNumber": "FR1319",
            }
        }
    ]
}


def test_parses_farfnd_response_into_offers():
    offers = parse_farfnd_response(RESPONSE, "BGY", source_name="ryanair-api")
    assert len(offers) == 1
    offer = offers[0]
    assert offer.legs[0].origin == "BGY"
    assert offer.legs[0].destination == "ATH"
    assert offer.legs[0].departure.date() == date(2027, 1, 18)
    assert offer.total_mandatory_eur == Decimal("43.98")
    assert offer.passengers == 2
    assert offer.verified is True


def test_provider_discovers_destinations_from_api(monkeypatch):
    import httpx

    class FakeTransport(httpx.MockTransport):
        def __init__(self):
            pass
        def handle_request(self, request):
            return httpx.Response(200, json=RESPONSE)

    provider = RyanairApiProvider(httpx.Client(transport=FakeTransport()))
    destinations = provider.destinations(("BGY",))
    assert "ATH" in destinations

    offers = provider.search("BGY", "ATH", date(2027, 1, 1), date(2027, 1, 31), 1, 2)
    assert len(offers) == 1
    assert offers[0].total_mandatory_eur == Decimal("43.98")
