from decimal import Decimal

import pytest

from flight_alert.pricing import normalize_currency, total_for_passengers


def test_converts_foreign_currency_to_eur():
    assert normalize_currency(Decimal("50"), "GBP", {"GBP": Decimal("1.17")}) == Decimal("58.50")


def test_multiplies_per_person_fare_for_two_passengers():
    assert total_for_passengers(Decimal("24.99"), 2, per_person=True) == Decimal("49.98")


def test_adds_mandatory_fees_before_multiplication():
    assert total_for_passengers(Decimal("20"), 2, per_person=True, mandatory_fees=Decimal("12")) == Decimal("52.00")


def test_rejects_missing_or_invalid_price():
    with pytest.raises(ValueError, match="price"):
        total_for_passengers(None, 2)
    with pytest.raises(ValueError, match="currency"):
        normalize_currency(Decimal("10"), "USD", {})
