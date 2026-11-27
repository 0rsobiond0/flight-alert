from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from flight_alert.models import FlightOffer
from flight_alert.storage import OfferStore, offer_fingerprint


class AlertPolicy:
    def should_send(self, offer: FlightOffer, store: OfferStore) -> bool:
        fingerprint = offer_fingerprint(offer)
        last = store.last_price(fingerprint)
        if last is None:
            return True
        return last - offer.total_mandatory_eur >= Decimal("10")


def format_offer(offer: FlightOffer) -> str:
    legs = "\n".join(
        f"{leg.origin} → {leg.destination} {leg.departure:%Y-%m-%d %H:%M} "
        f"({leg.carrier or 'compagnia n/d'})"
        for leg in offer.legs
    )
    baggage = "; ".join(filter(None, (leg.optional_baggage_note for leg in offer.legs))) or "non verificato"
    verification = "" if offer.verified else "\n⚠️ Prezzo da verificare prima dell'acquisto"
    return (
        f"✈️ Offerta voli\n{legs}\n"
        f"Soggiorno: {offer.nights} notti\n"
        f"Totale 2 persone: {offer.total_mandatory_eur:.2f} EUR\n"
        f"Per persona: {offer.total_mandatory_eur / offer.passengers:.2f} EUR\n"
        f"Fonte: {offer.source}\n"
        f"Bagaglio: {baggage}\n"
        f"Controllato: {offer.retrieved_at:%Y-%m-%d %H:%M UTC}"
        f"{verification}\n"
        f"Link: {offer.booking_url or 'non disponibile'}"
    )
