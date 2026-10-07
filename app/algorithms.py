from __future__ import annotations

import heapq
from time import perf_counter
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class Transfer:
    sender_id: str
    receiver_id: str
    amount: int


@dataclass(frozen=True, slots=True)
class OptimizationResult:
    transfers: list[Transfer]
    is_exact: bool
    reason: str


def validate_balances(balances: Mapping[str, int]) -> None:
    if any(not isinstance(value, int) for value in balances.values()):
        raise TypeError("Balances must be integer UZS amounts")
    if sum(balances.values()) != 0:
        raise ValueError("Balance invariant violated: group total must equal zero")


def greedy_transfers(balances: Mapping[str, int]) -> list[Transfer]:
    """Deterministic two-heap debt simplification, O(n log n)."""
    validate_balances(balances)
    debtors = [(value, member_id) for member_id, value in balances.items() if value < 0]
    creditors = [(-value, member_id) for member_id, value in balances.items() if value > 0]
    heapq.heapify(debtors)       # most negative balance first
    heapq.heapify(creditors)     # largest credit encoded as negative
    result: list[Transfer] = []

    while debtors and creditors:
        debt_value, debtor = heapq.heappop(debtors)
        credit_value, creditor = heapq.heappop(creditors)
        debt, credit = -debt_value, -credit_value
        amount = min(debt, credit)
        result.append(Transfer(debtor, creditor, amount))
        debt -= amount
        credit -= amount
        if debt:
            heapq.heappush(debtors, (-debt, debtor))
        if credit:
            heapq.heappush(creditors, (-credit, creditor))

    return result


def optimize_transfers(
    balances: Mapping[str, int],
    max_members: int = 12,
    time_limit_seconds: float = 0.5,
    node_limit: int = 200_000,
) -> OptimizationResult:
    """Bounded branch-and-bound; returns greedy safely if the budget is exhausted."""
    validate_balances(balances)
    debtors = sorted([(member, -amount) for member, amount in balances.items() if amount < 0])
    creditors = sorted([(member, amount) for member, amount in balances.items() if amount > 0])
    if len(debtors) + len(creditors) > max_members:
        return OptimizationResult(greedy_transfers(balances), False, "member_limit")

    best = greedy_transfers(balances)
    debt = [amount for _, amount in debtors]
    credit = [amount for _, amount in creditors]
    started = perf_counter()
    nodes = 0
    exhausted = False

    def search(di: int, path: list[Transfer]) -> None:
        nonlocal best, nodes, exhausted
        nodes += 1
        if nodes > node_limit or perf_counter() - started > time_limit_seconds:
            exhausted = True
            return
        while di < len(debt) and debt[di] == 0:
            di += 1
        if di == len(debt):
            if len(path) < len(best):
                best = path.copy()
            return
        if len(path) >= len(best):
            return
        seen: set[int] = set()
        for ci, available in enumerate(credit):
            if exhausted:
                return
            if available == 0 or available in seen:
                continue
            seen.add(available)
            amount = min(debt[di], available)
            debt[di] -= amount
            credit[ci] -= amount
            path.append(Transfer(debtors[di][0], creditors[ci][0], amount))
            search(di, path)
            path.pop()
            debt[di] += amount
            credit[ci] += amount
            if amount == available and amount == debt[di]:
                break

    search(0, [])
    return OptimizationResult(best, not exhausted, "exact" if not exhausted else "budget_exhausted")


def exact_transfers(balances: Mapping[str, int], max_members: int = 12) -> list[Transfer]:
    """Compatibility helper returning the best solution found within a safe budget."""
    return optimize_transfers(balances, max_members=max_members).transfers


def apply_transfers(balances: Mapping[str, int], transfers: list[Transfer]) -> dict[str, int]:
    remaining = dict(balances)
    for transfer in transfers:
        if transfer.amount <= 0:
            raise ValueError("Transfer amount must be positive")
        remaining[transfer.sender_id] += transfer.amount
        remaining[transfer.receiver_id] -= transfer.amount
    return remaining
