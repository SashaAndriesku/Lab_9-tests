import pytest
from rental.service import RentalService

pytestmark = pytest.mark.unit


class DummyRepo:
    pass


class DummyPolicy:
    def is_allowed(self, equipment, quantity, days):
        return True


@pytest.fixture
def service():
    return RentalService(DummyRepo(), DummyRepo(), DummyPolicy())


def test_calculate_total_without_discount(service):
    assert service.calculate_total(daily_rate=1000, quantity=2, days=3) == 6000


def test_calculate_total_with_seven_days_discount(service):
    assert service.calculate_total(daily_rate=1000, quantity=1, days=7) == 6300


def test_calculate_late_fee_returns_zero(service):
    assert service.calculate_late_fee(daily_rate=1500, quantity=1, days=3, overdue_days=2) == 0


def test_is_rental_allowed_valid_input(service):
    assert service.is_rental_allowed(daily_rate=500, quantity=2, days=5, premium=True) is True


@pytest.mark.parametrize(
    "daily_rate,quantity,days,premium",
    [
        (50, 1, 1, False),
        (1000, 0, 1, False),
        (1000, 21, 1, False),
        (1000, 1, 0, False),
        (1000, 1, 31, False),
        (1000, 1, 5, "yes"),
    ],
)
def test_calculate_total_invalid_arguments(service, daily_rate, quantity, days, premium):
    with pytest.raises(ValueError):
        service.calculate_total(daily_rate, quantity, days, premium)


def test_service_requires_all_dependencies():
    with pytest.raises(ValueError):
        RentalService(None, DummyRepo(), DummyPolicy())