from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from flight_alert.models import FlightOffer


class OfferStore:
    def __init__(self, path: Path):
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.path) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS offers (
                    fingerprint TEXT PRIMARY KEY,
                    price_eur TEXT NOT NULL,
                    seen_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
            """)

    def seen_recently(self, fingerprint: str, now: datetime, repeat_days: int = 7) -> bool:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT seen_at FROM offers WHERE fingerprint = ?", (fingerprint,)).fetchone()
        if row is None:
            return False
        seen_at = datetime.fromisoformat(row[0])
        return seen_at >= now - timedelta(days=repeat_days)

    def record(self, offer: FlightOffer, fingerprint: str, seen_at: datetime | None = None) -> None:
        timestamp = seen_at or datetime.now(timezone.utc)
        payload = {
            "source": offer.source,
            "total_mandatory_eur": str(offer.total_mandatory_eur),
            "verified": offer.verified,
            "booking_url": offer.booking_url,
            "baggage": [leg.optional_baggage_note for leg in offer.legs],
        }
        with sqlite3.connect(self.path) as db:
            db.execute(
                """INSERT INTO offers (fingerprint, price_eur, seen_at, source, payload)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(fingerprint) DO UPDATE SET
                     price_eur = excluded.price_eur, seen_at = excluded.seen_at,
                     source = excluded.source, payload = excluded.payload""",
                (fingerprint, str(offer.total_mandatory_eur), timestamp.isoformat(), offer.source, json.dumps(payload)),
            )

    def last_price(self, fingerprint: str) -> Decimal | None:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT price_eur FROM offers WHERE fingerprint = ?", (fingerprint,)).fetchone()
        return Decimal(row[0]) if row else None


def offer_fingerprint(offer: FlightOffer) -> str:
    parts = [offer.offer_type, offer.source, str(offer.nights)]
    parts.extend(
        f"{leg.origin}:{leg.destination}:{leg.departure.isoformat()}:{leg.arrival.isoformat()}:{leg.carrier}:{leg.flight_number}"
        for leg in offer.legs
    )
    return "|".join(parts)
