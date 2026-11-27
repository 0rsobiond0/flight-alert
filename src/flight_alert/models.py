from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Literal


@dataclass(frozen=True)
class FlightLeg:
    origin: str
    destination: str
    departure: datetime
    arrival: datetime
    carrier: str | None
    flight_number: str | None
    mandatory_total_eur: Decimal
    optional_baggage_note: str | None
    booking_url: str
    source: str
    retrieved_at: datetime
    verified: bool

    def __post_init__(self) -> None:
        if self.mandatory_total_eur is None or self.mandatory_total_eur < 0:
            raise ValueError("mandatory_total_eur must be present and non-negative")
        if not self.booking_url or not self.source:
            raise ValueError("booking_url and source are required")
        if self.arrival < self.departure:
            raise ValueError("arrival cannot precede departure")


@dataclass(frozen=True)
class FlightOffer:
    legs: tuple[FlightLeg, ...]
    nights: int
    passengers: int
    total_mandatory_eur: Decimal
    offer_type: Literal["round_trip", "separate_one_way"]
    source: str
    retrieved_at: datetime
    booking_url: str | None = None
    verification_note: str | None = None

    def __post_init__(self) -> None:
        if not self.legs:
            raise ValueError("at least one flight leg is required")
        if self.total_mandatory_eur is None or self.total_mandatory_eur < 0:
            raise ValueError("total_mandatory_eur must be present and non-negative")
        if self.nights <= 0 or self.passengers <= 0:
            raise ValueError("nights and passengers must be positive")
        if self.offer_type not in {"round_trip", "separate_one_way"}:
            raise ValueError("unsupported offer_type")
        if not self.source:
            raise ValueError("source is required")

    @property
    def verified(self) -> bool:
        return all(leg.verified for leg in self.legs)

    @property
    def departure_date(self) -> date:
        return min(leg.departure for leg in self.legs).date()
