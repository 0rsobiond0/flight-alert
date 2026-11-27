from datetime import date

from flight_alert.config import Settings
from flight_alert.search import SearchEngine


class CountingProvider:
    name = "counting"

    def __init__(self):
        self.calls = []

    def destinations(self, origins):
        return ["SKP"]

    def search(self, origin, destination, start_date, end_date, nights, passengers):
        self.calls.append((origin, destination, nights, passengers))
        return []


def test_reuses_one_way_queries_across_night_lengths():
    provider = CountingProvider()
    settings = Settings.from_env({"DRY_RUN": "true", "MIN_NIGHTS": "2", "MAX_NIGHTS": "4"})
    SearchEngine(provider, settings).run_cycle()
    assert provider.calls.count(("BGY", "SKP", 1, 2)) == 1
    assert provider.calls.count(("SKP", "BGY", 1, 2)) == 1
