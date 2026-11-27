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
                    notified_at TEXT,
                    notified_price_eur TEXT,
                    source TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
            """)
            columns = {row[1] for row in db.execute("PRAGMA table_info(offers)")}
            if "notified_at" not in columns:
                db.execute("ALTER TABLE offers ADD COLUMN notified_at TEXT")
            if "notified_price_eur" not in columns:
                db.execute("ALTER TABLE offers ADD COLUMN notified_price_eur TEXT")

    def seen_recently(self, fingerprint: str, now: datetime, repeat_days: int = 7) -> bool:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT seen_at FROM offers WHERE fingerprint = ?", (fingerprint,)).fetchone()
        if row is None:
            return False
        return datetime.fromisoformat(row[0]) >= now - timedelta(days=repeat_days)

    def record(self, offer: FlightOffer, fingerprint: str, seen_at: datetime | None = None, notified_at: datetime | None = None) -> None:
        timestamp = seen_at or datetime.now(timezone.utc)
        payload = {
            "source": offer.source,
            "total_mandatory_eur": str(offer.total_mandatory_eur),
            "verified": offer.verified,
            "booking_url": offer.booking_url,
            "baggage": [leg.optional_baggage_note for leg in offer.legs],
        }
        with sqlite3.connect(self.path) as db:
            old = db.execute("SELECT notified_at, notified_price_eur FROM offers WHERE fingerprint = ?", (fingerprint,)).fetchone()
            saved_notified_at = notified_at.isoformat() if notified_at else (old[0] if old else None)
            saved_notified_price = str(offer.total_mandatory_eur) if notified_at else (old[1] if old else None)
            db.execute(
                """INSERT INTO offers (fingerprint, price_eur, seen_at, notified_at, notified_price_eur, source, payload)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(fingerprint) DO UPDATE SET
                     price_eur=excluded.price_eur, seen_at=excluded.seen_at,
                     notified_at=excluded.notified_at, notified_price_eur=excluded.notified_price_eur,
                     source=excluded.source, payload=excluded.payload""",
                (fingerprint, str(offer.total_mandatory_eur), timestamp.isoformat(), saved_notified_at, saved_notified_price, offer.source, json.dumps(payload)),
            )

    def last_price(self, fingerprint: str) -> Decimal | None:
        return self._price(fingerprint, "price_eur")

    def last_notified_price(self, fingerprint: str) -> Decimal | None:
        return self._price(fingerprint, "notified_price_eur")

    def last_notified_at(self, fingerprint: str) -> datetime | None:
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT notified_at FROM offers WHERE fingerprint = ?", (fingerprint,)).fetchone()
        return datetime.fromisoformat(row[0]) if row and row[0] else None

    def _price(self, fingerprint: str, column: str) -> Decimal | None:
        with sqlite3.connect(self.path) as db:
            row = db.execute(f"SELECT {column} FROM offers WHERE fingerprint = ?", (fingerprint,)).fetchone()
        return Decimal(row[0]) if row and row[0] is not None else None


def offer_fingerprint(offer: FlightOffer) -> str:
    parts = [offer.offer_type, offer.source, str(offer.nights)]
    parts.extend(
        f"{leg.origin}:{leg.destination}:{leg.departure.isoformat()}:{leg.arrival.isoformat()}:{leg.carrier}:{leg.flight_number}"
        for leg in offer.legs
    )
    return "|".join(parts)
