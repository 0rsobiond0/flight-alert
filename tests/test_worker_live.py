from pathlib import Path

from flight_alert.config import Settings
from flight_alert.worker import build_provider, run_once


def test_empty_dry_run_is_offline(tmp_path):
    settings = Settings.from_env({"DRY_RUN": "true", "STATE_DB": str(tmp_path / "offers.db")})
    report = run_once(settings)
    assert report.destinations_checked == 0
    assert report.queries_completed == 0
