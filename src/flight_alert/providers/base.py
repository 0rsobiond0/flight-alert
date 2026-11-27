from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from flight_alert.models import FlightOffer


class FlightProvider(ABC):
    name: str

    @abstractmethod
    def destinations(self, origins: tuple[str, ...]) -> list[str]:
        raise NotImplementedError

    @abstractmethod
    def search(
        self,
        origin: str,
        destination: str | None,
        start_date: date,
        end_date: date,
        nights: int,
        passengers: int,
    ) -> list[FlightOffer]:
        raise NotImplementedError
