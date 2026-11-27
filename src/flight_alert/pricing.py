from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Mapping

_CENTS = Decimal("0.01")


def normalize_currency(amount: Decimal, currency: str, rates: Mapping[str, Decimal]) -> Decimal:
    if amount is None or amount < 0:
        raise ValueError("price must be a non-negative amount")
    normalized = currency.strip().upper()
    if normalized == "EUR":
        rate = Decimal("1")
    else:
        try:
            rate = rates[normalized]
        except KeyError as exc:
            raise ValueError(f"currency {normalized} has no conversion rate") from exc
    if rate <= 0:
        raise ValueError("currency conversion rate must be positive")
    return (amount * rate).quantize(_CENTS, rounding=ROUND_HALF_UP)


def total_for_passengers(
    price: Decimal | None,
    passengers: int,
    *,
    per_person: bool = False,
    mandatory_fees: Decimal = Decimal("0"),
) -> Decimal:
    if price is None or price < 0:
        raise ValueError("price must be a non-negative amount")
    if passengers <= 0:
        raise ValueError("passengers must be positive")
    if mandatory_fees < 0:
        raise ValueError("mandatory fees must be non-negative")
    total = price * passengers if per_person else price
    return (total + mandatory_fees).quantize(_CENTS, rounding=ROUND_HALF_UP)
