from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import httpx

from flight_alert.models import FlightLeg, FlightOffer
from flight_alert.providers.base import FlightProvider

API_BASE = "https://services-api.ryanair.com/farfnd/v4/oneWayFares"


def parse_farfnd_response(payload: dict[str, Any], origin: str, source_name: str = "ryanair-api") -> list[FlightOffer]:
    now = datetime.now(timezone.utc)
    offers: list[FlightOffer] = []
    for item in payload.get("fares", []):
        try:
            ob = item["outbound"]
            iata_origin = ob["departureAirport"]["iataCode"].upper()
            iata_dest = ob["arrivalAirport"]["iataCode"].upper()
            departure = datetime.fromisoformat(ob["departureDate"]).replace(tzinfo=timezone.utc)
            arrival = datetime.fromisoformat(ob["arrivalDate"]).replace(tzinfo=timezone.utc)
            price = Decimal(str(ob["price"]["value"]))
            flight_number = ob.get("flightNumber")
            url = (
                f"https://www.ryanair.com/ie/en/trip/flights/select"
                f"?adults=2&dateOut={departure.date()}&originIata={iata_origin}&destinationIata={iata_dest}"
            )
        except (KeyError, TypeError, ValueError):
            continue
        leg = FlightLeg(
            origin=iata_origin,
            destination=iata_dest,
            departure=departure,
            arrival=arrival,
            carrier="FR",
            flight_number=flight_number,
            mandatory_total_eur=price,
            optional_baggage_note="small personal item included; cabin bag extra",
            booking_url=url,
            source=source_name,
            retrieved_at=now,
            verified=True,
        )
        offers.append(FlightOffer(
            legs=(leg,),
            nights=1,
            passengers=2,
            total_mandatory_eur=price,
            offer_type="separate_one_way",
            source=source_name,
            retrieved_at=now,
            booking_url=url,
            verification_note="Ryanair published fare for 2 adults; verify total at checkout",
        ))
    return offers


class RyanairApiProvider(FlightProvider):
    name = "ryanair-api"

    def __init__(self, http_client: httpx.Client, max_routes: int = 100, offline: bool = False):
        self.http_client = http_client
        self.max_routes = max_routes
        self.offline = offline
        self._cache: dict[tuple[str, str, str, str], list[FlightOffer]] = {}
        self._destinations: dict[str, list[str]] = {}

    def _fetch(self, origin: str, destination: str | None, date_from: date, date_to: date) -> list[FlightOffer]:
        key = (origin, destination or "", str(date_from), str(date_to))
        if key in self._cache:
            return self._cache[key]
        params: dict[str, str] = {
            "departureAirportIataCode": origin,
            "outboundDepartureDateFrom": str(date_from),
            "outboundDepartureDateTo": str(date_to),
            "currency": "EUR",
            "adultPaxCount": "2",
        }
        if destination:
            params["arrivalAirportIataCode"] = destination
        response = self.http_client.get(API_BASE, params=params, timeout=30)
        response.raise_for_status()
        result = parse_farfnd_response(response.json(), origin, self.name)
        self._cache[key] = result
        return result

    def destinations(self, origins: tuple[str, ...]) -> list[str]:
        if self.offline:
            return []
        result: set[str] = set()
        today = date.today()
        for origin in origins:
            if origin in self._destinations:
                result.update(self._destinations[origin])
                continue
            from flight_alert.config import Settings
            import os
            end = date.fromisoformat(os.environ.get("SEARCH_UNTIL", "2027-03-31"))
            offers = self._fetch(origin, None, today, end)
            dests = sorted({offer.legs[0].destination for offer in offers})
            self._destinations[origin] = dests
            result.update(dests)
        return sorted(result)

    def search(self, origin: str, destination: str | None, start_date: date, end_date: date, nights: int, passengers: int) -> list[FlightOffer]:
        offers = self._fetch(origin, destination, start_date, end_date)
        return [
            o for o in offers
            if (destination is None or o.legs[0].destination == destination)
            and start_date <= o.legs[0].departure.date() <= end_date
            and o.passengers == passengers
        ]
