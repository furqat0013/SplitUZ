import pytest

from app.algorithms import apply_transfers, exact_transfers, greedy_transfers, optimize_transfers
from app.services import split_amount


@pytest.mark.parametrize("balances", [
    {"a": -70, "b": -30, "c": 100},
    {"a": -40, "b": -60, "c": 25, "d": 75},
    {"a": 0, "b": 0},
])
def test_greedy_zeroes_every_balance(balances):
    transfers = greedy_transfers(balances)
    assert all(value == 0 for value in apply_transfers(balances, transfers).values())
    nonzero = sum(value != 0 for value in balances.values())
    assert len(transfers) <= max(0, nonzero - 1)


def test_invalid_group_total_is_rejected():
    with pytest.raises(ValueError):
        greedy_transfers({"a": 10, "b": -9})


def test_exact_is_never_worse_than_greedy():
    balances = {"a": -8, "b": -7, "c": -5, "d": 10, "e": 10}
    assert len(exact_transfers(balances)) <= len(greedy_transfers(balances))
    assert all(value == 0 for value in apply_transfers(balances, exact_transfers(balances)).values())


def test_round_robin_remainder_is_deterministic():
    assert split_amount(10, [1, 1, 1]) == [4, 3, 3]
    assert split_amount(7, [50, 30, 20]) == [4, 2, 1]
    assert split_amount(10, [100, 0]) == [10, 0]


def test_exact_has_safe_budget_fallback():
    balances = {"a": -8, "b": -7, "c": -5, "d": 10, "e": 10}
    result = optimize_transfers(balances, time_limit_seconds=0, node_limit=0)
    assert result.is_exact is False
    assert result.reason == "budget_exhausted"
    assert all(value == 0 for value in apply_transfers(balances, result.transfers).values())
