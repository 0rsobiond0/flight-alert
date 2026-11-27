from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Sequence

from flight_alert.config import Settings
from flight_alert.models import FlightLeg, FlightOffer
from flight_alert.providers.base import FlightProvider


@dataclass(frozen=True)
class SearchReport:
    offers: list[FlightOffer]
    destinations_checked: int
    queries_completed: int
    queries_skipped: int
    provider_errors: list[str]


def combine_one_way(
    outbound: Sequence[FlightOffer],
    inbound: Sequence[FlightOffer],
    min_nights: int,
    max_nights: int,
) -> list[FlightOffer]:
    combined: list[FlightOffer] = []
    for out in outbound:
        if len(out.legs) != 1:
            continue
        out_leg = out.legs[0]
        for back in inbound:
            if len(back.legs) != 1:
                continue
            back_leg = back.legs[0]
            nights = (back_leg.departure.date() - out_leg.departure.date()).days
            if (
                out_leg.destination != back_leg.origin
                or out_leg.origin != back_leg.destination
                or not min_nights <= nights <= max_nights
                or back_leg.departure <= out_leg.arrival
            ):
                continue
            combined.append(
                FlightOffer(
                    legs=(out_leg, back_leg),
                    nights=nights,
                    passengers=min(out.passengers, back.passengers),
                    total_mandatory_eur=(out.total_mandatory_eur + back.total_mandatory_eur).quantize(Decimal("0.01")),
                    offer_type="separate_one_way",
                    source=f"{out.source}+{back.source}",
                    retrieved_at=max(out.retrieved_at, back.retrieved_at),
                    booking_url=f"{out.booking_url or out_leg.booking_url}\n{back.booking_url or back_leg.booking_url}",
                    verification_note="separate tickets; verify each booking independently",
                )
            )
    return combined


class SearchEngine:
    def __init__(self, provider: FlightProvider, settings: Settings):
        self.provider = provider
        self.settings = settings

    def run_cycle(self) -> SearchReport:
        destinations = self.provider.destinations(self.settings.origins)
        offers: list[FlightOffer] = []
        errors: list[str] = []
        completed = 0
        skipped = 0
        start = date.today()
        end = self.settings.search_until
        for destination in destinations:
            for origin in self.settings.origins:
                for nights in range(self.settings.min_nights, self.settings.max_nights + 1):
                    try:
                        direct = self.provider.search(origin, destination, start, end, nights, self.settings.passengers)
                        completed += 1
                        offers.extend(
                            offer for offer in direct if offer.total_mandatory_eur <= self.settings.max_total_eur
                        )
                        outbound = self.provider.search(origin, destination, start, end, 1, self.settings.passengers)
                        inbound = self.provider.search(destination, origin, start, end, 1, self.settings.passengers)
                        completed += 2
                        offers.extend(
                            offer
                            for offer in combine_one_way(
                                outbound, inbound, self.settings.min_nights, self.settings.max_nights
                            )
                            if offer.nights == nights and offer.total_mandatory_eur <= self.settings.max_total_eur
                        )
                    except Exception as exc:  # provider isolation is intentional
                        errors.append(f"{self.provider.name}:{origin}->{destination}:{exc}")
                        skipped += 1
        return SearchReport(offers, len(destinations), completed, skipped, errors)
