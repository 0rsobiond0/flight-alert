from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from flight_alert.models import FlightOffer
from flight_alert.storage import OfferStore, offer_fingerprint


class AlertPolicy:
    def should_send(self, offer: FlightOffer, store: OfferStore, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        fingerprint = offer_fingerprint(offer)
        notified_at = store.last_notified_at(fingerprint)
        notified_price = store.last_notified_price(fingerprint)
        if notified_at is None or notified_price is None:
            return True
        if now - notified_at >= timedelta(days=7):
            return True
        return notified_price - offer.total_mandatory_eur >= Decimal("10")


def format_offer(offer: FlightOffer) -> str:
    legs = "\n".join(
        f"{leg.origin} → {leg.destination} {leg.departure:%Y-%m-%d %H:%M}–{leg.arrival:%H:%M} "
        f"({leg.carrier or 'compagnia n/d'}{(' ' + leg.flight_number) if leg.flight_number else ''})"
        for leg in offer.legs
    )
    baggage = "; ".join(filter(None, (leg.optional_baggage_note for leg in offer.legs))) or "non verificato"
    verification = offer.verification_note or ("" if offer.verified else "Prezzo da verificare prima dell'acquisto")
    return (
        f"✈️ Offerta voli\n{legs}\n"
        f"Soggiorno: {offer.nights} notti\n"
        f"Totale {offer.passengers} persone: {offer.total_mandatory_eur:.2f} EUR\n"
        f"Per persona: {offer.total_mandatory_eur / offer.passengers:.2f} EUR\n"
        f"Fonte: {offer.source}\nBagaglio: {baggage}\n"
        f"Controllato: {offer.retrieved_at:%Y-%m-%d %H:%M UTC}\n"
        f"{('⚠️ ' + verification + chr(10)) if verification else ''}"
        f"Link: {offer.booking_url or 'non disponibile'}"
    )
