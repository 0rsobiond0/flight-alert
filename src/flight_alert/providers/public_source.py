from __future__ import annotations

import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

from flight_alert.models import FlightLeg, FlightOffer
from flight_alert.pricing import total_for_passengers, normalize_currency
from flight_alert.providers.base import FlightProvider


class PublicSourceProvider(FlightProvider):
    def __init__(self, http_client: httpx.AsyncClient | None = None, base_url: str = "", *, payload=None, source_name="public-source"):
        self.http_client = http_client
        self.base_url = base_url
        self.payload = payload
        self.name = source_name

    @classmethod
    def from_payload(cls, payload: dict[str, Any], source_name: str = "public-source") -> "PublicSourceProvider":
        normalized = parse_public_payload(payload, source_name)
        return cls(payload=normalized, source_name=source_name)

    def destinations(self, origins: tuple[str, ...]) -> list[str]:
        return list(self.payload["destinations"] if self.payload else [])

    def search(self, origin, destination, start_date, end_date, nights, passengers):
        if not self.payload:
            raise RuntimeError("live browser adapter requires an explicit public source payload")
        results = []
        for offer in self.payload["offers"]:
            leg = offer.legs[0]
            if leg.origin != origin or leg.destination != destination:
                continue
            if not start_date <= leg.departure.date() <= end_date:
                continue
            results.append(offer)
        return results

    async def fetch_payload(self) -> dict[str, Any]:
        if not self.http_client or not self.base_url:
            raise RuntimeError("base_url and http_client are required")
        response = await self.http_client.get(self.base_url, timeout=30)
        response.raise_for_status()
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise ValueError("public source did not return JSON payload") from exc
        return parse_public_payload(payload, self.name)


def parse_public_payload(payload: dict[str, Any], source_name: str) -> dict[str, Any]:
    if not isinstance(payload, dict) or not isinstance(payload.get("offers"), list):
        raise ValueError("public payload must contain an offers list")
    destinations = payload.get("destinations", [])
    if not isinstance(destinations, list):
        raise ValueError("destinations must be a list")
    offers = []
    retrieved = datetime.now(timezone.utc)
    for item in payload["offers"]:
        if not isinstance(item, dict):
            raise ValueError("offer must be an object")
        required = ("origin", "destination", "departure", "arrival", "price", "currency", "booking_url")
        if any(key not in item for key in required):
            raise ValueError("offer price and flight fields are required")
        price = Decimal(str(item["price"]))
        currency = str(item["currency"]).upper()
        if currency != "EUR":
            raise ValueError("non-EUR live payload requires configured exchange rates")
        total = total_for_passengers(
            price,
            int(item.get("passengers", 2)),
            per_person=bool(item.get("per_person", False)),
            mandatory_fees=Decimal(str(item.get("mandatory_fees", "0"))),
        )
        departure = datetime.fromisoformat(item["departure"])
        arrival = datetime.fromisoformat(item["arrival"])
        leg = FlightLeg(
            origin=str(item["origin"]).upper(),
            destination=str(item["destination"]).upper(),
            departure=departure,
            arrival=arrival,
            carrier=item.get("carrier"),
            flight_number=item.get("flight_number"),
            mandatory_total_eur=total,
            optional_baggage_note=item.get("baggage_note"),
            booking_url=str(item["booking_url"]),
            source=source_name,
            retrieved_at=retrieved,
            verified=bool(item.get("verified", False)),
        )
        offers.append(
            FlightOffer(
                legs=(leg,),
                nights=1,
                passengers=int(item.get("passengers", 2)),
                total_mandatory_eur=total,
                offer_type="separate_one_way",
                source=source_name,
                retrieved_at=retrieved,
                booking_url=leg.booking_url,
                verification_note=None if leg.verified else "public price requires final verification",
            )
        )
    return {"destinations": [str(value).upper() for value in destinations], "offers": offers}
