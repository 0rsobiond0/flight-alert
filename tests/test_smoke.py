from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from flight_alert.alerts import format_offer
from flight_alert.config import Settings
from flight_alert.models import FlightLeg, FlightOffer
from flight_alert.storage import OfferStore


def test_offline_dry_run_smoke(tmp_path, monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    settings = Settings.from_env()
    store = OfferStore(tmp_path / "offers.db")
    store.initialize()
    now = datetime.now(timezone.utc)
    leg = FlightLeg("BGY", "SKP", now, now, "W6", "1", Decimal("80"), "small bag", "https://example", "fixture", now, True)
    text = format_offer(FlightOffer((leg,), 2, settings.passengers, Decimal("80"), "round_trip", "fixture", now, "https://example"))
    assert "80.00 EUR" in text
    assert (tmp_path / "offers.db").exists()
    installer = Path(__file__).parents[1] / "deploy" / "install-lxc.sh"
    assert installer.exists()
    assert installer.stat().st_mode & 0o111
