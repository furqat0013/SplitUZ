from __future__ import annotations

import csv
import io
from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.algorithms import greedy_transfers, optimize_transfers
from app.models import Expense, ExpenseShare, Group, Member, Settlement


REQUIRED_FILES = {
    "groups.csv": {"group_id", "nomi", "turi", "valyuta", "yaratilgan"},
    "members.csv": {"group_id", "member_id", "ism", "bank", "qoshilgan"},
    "expenses.csv": {"expense_id", "group_id", "tolagan_member_id", "summa", "valyuta", "kategoriya", "izoh", "bolish_usuli", "sana", "ochirilgan"},
    "expense_shares.csv": {"expense_id", "group_id", "member_id", "ulush"},
    "settlements.csv": {"settlement_id", "group_id", "kimdan", "kimga", "summa", "sana", "holat"},
}
MAX_ROWS_PER_FILE = 250_000
MAX_MONEY = 9_223_372_036_854_775_807
SPLIT_METHODS = {"teng", "foiz", "aniq", "pozitsiya"}
CONFIRMED_STATUS = "tasdiqlangan"
CONFIRMED_TOKENS = {"tasdiqlangan", "tasdiqlandi", "confirmed", "completed", "success", "ok", "done", "tolangan", "yopilgan"}
UNCONFIRMED_TOKENS = {"kutilmoqda", "pending", "bekor", "bekorqilingan", "cancelled", "canceled", "failed", "radetilgan", "rad"}
DELETED_FALSE = {"yoq", "false", "0", "no", "n", "f", "aktiv"}
DELETED_TRUE = {"ha", "true", "1", "yes", "y", "t", "ochirilgan", "ochirildi"}
OPTIONAL_COLUMNS = {"expenses.csv": {"izoh"}}


_APOSTROPHES = str.maketrans({"\u2018": "", "\u2019": "", "\u02bb": "", "\u02bc": "", "`": "", "'": ""})


def normalize_token(value: str) -> str:
    return str(value).strip().lower().translate(_APOSTROPHES).replace("_", "").replace(" ", "")


def parse_deleted(value: str) -> bool:
    token = normalize_token(value)
    if token in DELETED_FALSE:
        return False
    if token in DELETED_TRUE:
        return True
    raise ValueError(f"Unknown ochirilgan value: {value!r}")


def parse_settlement_status(value: str) -> str:
    token = normalize_token(value)
    if token in CONFIRMED_TOKENS:
        return CONFIRMED_STATUS
    if token in UNCONFIRMED_TOKENS:
        return "tasdiqlanmagan"
    raise ValueError(f"Unknown settlement status: {value!r}")


def parse_money(value: str, field: str) -> int:
    token = str(value).strip().replace("\u00a0", "").replace(" ", "")
    if "," in token and "." in token:
        token = token.replace(",", "")
    elif token.count(",") == 1 and len(token.rsplit(",", 1)[1]) <= 2:
        token = token.replace(",", ".")
    else:
        token = token.replace(",", "")
    try:
        number = Decimal(token)
    except InvalidOperation as exc:
        raise ValueError(f"{field}: invalid integer UZS amount {value!r}") from exc
    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError(f"{field}: whole UZS amount required, got {value!r}")
    return int(number)


def parse_date(value: str, field: str, with_time: bool = False):
    token = str(value).strip().replace("Z", "").replace("T", " ")
    formats = ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d")
    try:
        parsed = datetime.fromisoformat(token)
    except ValueError:
        parsed = None
        for fmt in formats:
            try:
                parsed = datetime.strptime(token, fmt)
                break
            except ValueError:
                continue
    if parsed is None:
        raise ValueError(f"{field}: unsupported date {value!r}")
    return parsed if with_time else parsed.date()


def _rows(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        actual = set(reader.fieldnames or [])
        if missing := required - actual:
            raise ValueError(f"{path.name}: missing columns {sorted(missing)}")
        if extra := actual - required:
            raise ValueError(f"{path.name}: unexpected columns {sorted(extra)}")
        rows = []
        for index, row in enumerate(reader, start=2):
            if index > MAX_ROWS_PER_FILE:
                raise ValueError(f"{path.name}: exceeds {MAX_ROWS_PER_FILE} row limit")
            if None in row or any(isinstance(value, list) for value in row.values()):
                raise ValueError(f"{path.name}:{index}: malformed CSV row")
            rows.append(row)
    required_values = required - OPTIONAL_COLUMNS.get(path.name, set())
    if any(any(row.get(column) is None or row[column].strip() == "" for column in required_values) for row in rows):
        raise ValueError(f"{path.name}: required values must not be blank")
    return rows


def import_dataset(db: Session, directory: Path) -> dict[str, int]:
    """Atomically replace current data after full CSV validation."""
    raw = {name: _rows(directory / name, columns) for name, columns in REQUIRED_FILES.items()}
    group_ids = {row["group_id"] for row in raw["groups.csv"]}
    group_currencies = {row["group_id"]: row["valyuta"] for row in raw["groups.csv"]}
    member_keys = {(row["group_id"], row["member_id"]) for row in raw["members.csv"]}
    expense_ids = {row["expense_id"] for row in raw["expenses.csv"]}
    if len(group_ids) != len(raw["groups.csv"]) or len(member_keys) != len(raw["members.csv"]) or len(expense_ids) != len(raw["expenses.csv"]):
        raise ValueError("Duplicate primary keys detected")

    for row in raw["members.csv"]:
        if row["group_id"] not in group_ids:
            raise ValueError(f"Unknown member group: {row['group_id']}")
    member_counts = defaultdict(int)
    for group_id, _ in member_keys:
        member_counts[group_id] += 1
    if invalid_groups := {group_id: member_counts[group_id] for group_id in group_ids if not 3 <= member_counts[group_id] <= 12}:
        raise ValueError(f"Groups must contain 3..12 members: {invalid_groups}")
    expense_amounts: dict[str, int] = {}
    expense_groups: dict[str, str] = {}
    for row in raw["expenses.csv"]:
        amount = parse_money(row["summa"], f"{row['expense_id']}.summa")
        if amount <= 0 or amount > MAX_MONEY or (row["group_id"], row["tolagan_member_id"]) not in member_keys:
            raise ValueError(f"Invalid expense: {row['expense_id']}")
        if row["bolish_usuli"] not in SPLIT_METHODS:
            raise ValueError(f"Unknown split method in {row['expense_id']}: {row['bolish_usuli']}")
        if row["valyuta"] != group_currencies[row["group_id"]]:
            raise ValueError(f"Currency mismatch in expense: {row['expense_id']}")
        parse_deleted(row["ochirilgan"])
        expense_amounts[row["expense_id"]] = amount
        expense_groups[row["expense_id"]] = row["group_id"]

    share_totals: dict[str, int] = defaultdict(int)
    share_keys: set[tuple[str, str]] = set()
    for row in raw["expense_shares.csv"]:
        key = (row["expense_id"], row["member_id"])
        share = parse_money(row["ulush"], f"{row['expense_id']}.{row['member_id']}.ulush")
        if key in share_keys or row["expense_id"] not in expense_ids or (row["group_id"], row["member_id"]) not in member_keys:
            raise ValueError(f"Invalid or duplicate expense share: {key}")
        if row["group_id"] != expense_groups[row["expense_id"]]:
            raise ValueError(f"Share group does not match expense group: {row['expense_id']}")
        if share < 0 or share > MAX_MONEY:
            raise ValueError(f"Share must be a non-negative BIGINT: {key}")
        share_keys.add(key)
        share_totals[row["expense_id"]] += share
    for expense_id, amount in expense_amounts.items():
        if share_totals[expense_id] != amount:
            raise ValueError(f"Shares for {expense_id} sum to {share_totals[expense_id]}, expected {amount}")

    settlement_ids = {row["settlement_id"] for row in raw["settlements.csv"]}
    if len(settlement_ids) != len(raw["settlements.csv"]):
        raise ValueError("Duplicate settlement_id detected")
    for row in raw["settlements.csv"]:
        sender = (row["group_id"], row["kimdan"])
        receiver = (row["group_id"], row["kimga"])
        settlement_amount = parse_money(row["summa"], f"{row['settlement_id']}.summa")
        if sender not in member_keys or receiver not in member_keys or sender == receiver or settlement_amount <= 0 or settlement_amount > MAX_MONEY:
            raise ValueError(f"Invalid settlement: {row['settlement_id']}")
        parse_settlement_status(row["holat"])

    with db.begin_nested():
        for model in (ExpenseShare, Settlement, Expense, Member, Group):
            db.execute(delete(model))
        db.add_all([Group(id=r["group_id"], name=r["nomi"], kind=r["turi"], currency=r["valyuta"], created_at=parse_date(r["yaratilgan"], f"{r['group_id']}.yaratilgan")) for r in raw["groups.csv"]])
        db.flush()
        db.add_all([Member(group_id=r["group_id"], id=r["member_id"], name=r["ism"], bank=r["bank"], joined_at=parse_date(r["qoshilgan"], f"{r['member_id']}.qoshilgan")) for r in raw["members.csv"]])
        db.flush()
        db.add_all([Expense(id=r["expense_id"], group_id=r["group_id"], paid_by=r["tolagan_member_id"], amount=parse_money(r["summa"], f"{r['expense_id']}.summa"), currency=r["valyuta"], category=r["kategoriya"], note=r["izoh"], split_method=r["bolish_usuli"], spent_at=parse_date(r["sana"], f"{r['expense_id']}.sana", with_time=True), deleted=parse_deleted(r["ochirilgan"])) for r in raw["expenses.csv"]])
        db.flush()
        db.add_all([ExpenseShare(expense_id=r["expense_id"], group_id=r["group_id"], member_id=r["member_id"], amount=parse_money(r["ulush"], f"{r['expense_id']}.{r['member_id']}.ulush")) for r in raw["expense_shares.csv"]])
        db.add_all([Settlement(id=r["settlement_id"], group_id=r["group_id"], sender_id=r["kimdan"], receiver_id=r["kimga"], amount=parse_money(r["summa"], f"{r['settlement_id']}.summa"), settled_at=parse_date(r["sana"], f"{r['settlement_id']}.sana"), status=parse_settlement_status(r["holat"])) for r in raw["settlements.csv"]])
    db.commit()
    return {"groups": len(group_ids), "members": len(member_keys), "expenses": len(expense_ids), "shares": len(share_keys), "settlements": len(raw["settlements.csv"])}


def group_balances(db: Session, group_id: str) -> dict[str, int]:
    members = db.execute(select(Member.id).where(Member.group_id == group_id).order_by(Member.id)).scalars().all()
    balances = {member_id: 0 for member_id in members}
    paid = db.execute(select(Expense.paid_by, func.sum(Expense.amount)).where(Expense.group_id == group_id, Expense.deleted.is_(False)).group_by(Expense.paid_by)).all()
    owed = db.execute(select(ExpenseShare.member_id, func.sum(ExpenseShare.amount)).join(Expense, Expense.id == ExpenseShare.expense_id).where(ExpenseShare.group_id == group_id, Expense.deleted.is_(False)).group_by(ExpenseShare.member_id)).all()
    for member_id, amount in paid:
        balances[member_id] += int(amount)
    for member_id, amount in owed:
        balances[member_id] -= int(amount)
    settlements = db.execute(select(Settlement.sender_id, Settlement.receiver_id, Settlement.amount).where(Settlement.group_id == group_id, Settlement.status == "tasdiqlangan")).all()
    for sender, receiver, amount in settlements:
        balances[sender] += int(amount)
        balances[receiver] -= int(amount)
    if sum(balances.values()) != 0:
        raise RuntimeError(f"Invariant failed for {group_id}: {sum(balances.values())}")
    return balances


def all_balances(db: Session) -> dict[str, dict[str, int]]:
    # Set-based aggregation: four queries total instead of four queries per group.
    member_rows = db.execute(select(Member.group_id, Member.id).order_by(Member.group_id, Member.id)).all()
    balances: dict[str, dict[str, int]] = {}
    for group_id, member_id in member_rows:
        balances.setdefault(group_id, {})[member_id] = 0
    paid = db.execute(select(Expense.group_id, Expense.paid_by, func.sum(Expense.amount)).where(Expense.deleted.is_(False)).group_by(Expense.group_id, Expense.paid_by)).all()
    owed = db.execute(select(ExpenseShare.group_id, ExpenseShare.member_id, func.sum(ExpenseShare.amount)).join(Expense, Expense.id == ExpenseShare.expense_id).where(Expense.deleted.is_(False)).group_by(ExpenseShare.group_id, ExpenseShare.member_id)).all()
    settlements = db.execute(select(Settlement.group_id, Settlement.sender_id, Settlement.receiver_id, Settlement.amount).where(Settlement.status == CONFIRMED_STATUS)).all()
    for group_id, member_id, amount in paid:
        balances[group_id][member_id] += int(amount)
    for group_id, member_id, amount in owed:
        balances[group_id][member_id] -= int(amount)
    for group_id, sender, receiver, amount in settlements:
        balances[group_id][sender] += int(amount)
        balances[group_id][receiver] -= int(amount)
    invalid = {group_id: sum(group.values()) for group_id, group in balances.items() if sum(group.values()) != 0}
    if invalid:
        raise RuntimeError(f"Balance invariant failed: {invalid}")
    return balances


def export_balances(db: Session, output: Path) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.{uuid4().hex}.tmp")
    rows = all_balances(db)
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["group_id", "member_id", "net_balans"])
        for group_id, balances in rows.items():
            for member_id, amount in balances.items():
                writer.writerow([group_id, member_id, amount])
    temporary.replace(output)
    return sum(map(len, rows.values()))


def split_amount(amount: int, weights: list[int]) -> list[int]:
    """Largest-remainder allocation; equal weights implement round-robin residue."""
    if amount <= 0 or not weights or any(weight < 0 for weight in weights) or sum(weights) <= 0:
        raise ValueError("Amount must be positive and weights non-negative with a positive total")
    total = sum(weights)
    floors = [amount * weight // total for weight in weights]
    remainder = amount - sum(floors)
    order = sorted(range(len(weights)), key=lambda i: (-(amount * weights[i] % total), i))
    for index in order[:remainder]:
        floors[index] += 1
    return floors


def add_expense(db: Session, group_id: str, paid_by: str, amount: int, category: str, note: str, method: str, participants: list[str], values: list[int] | None = None) -> str:
    # Locks the group row in PostgreSQL, serializing concurrent writes per group.
    group = db.execute(select(Group).where(Group.id == group_id).with_for_update()).scalar_one_or_none()
    if group is None:
        raise ValueError(f"Unknown group: {group_id}")
    valid_members = set(db.execute(select(Member.id).where(Member.group_id == group_id)).scalars())
    if paid_by not in valid_members or not participants or len(set(participants)) != len(participants) or not set(participants) <= valid_members:
        raise ValueError("Invalid payer or participants")
    ordered = sorted(participants)
    if method == "teng":
        shares = split_amount(amount, [1] * len(ordered))
    elif method == "foiz":
        if values is None or len(values) != len(participants) or any(value < 0 for value in values) or sum(values) != 100:
            raise ValueError("Percentages must total 100")
        mapping = dict(zip(participants, values))
        shares = split_amount(amount, [mapping[m] for m in ordered])
    elif method in {"aniq", "pozitsiya"}:
        if values is None or len(values) != len(participants) or any(value < 0 for value in values) or sum(values) != amount:
            raise ValueError("Exact/position amounts must total expense amount")
        mapping = dict(zip(participants, values))
        shares = [mapping[m] for m in ordered]
    else:
        raise ValueError("Unsupported split method")
    expense_id = f"UI-{uuid4().hex}"
    db.add(Expense(id=expense_id, group_id=group_id, paid_by=paid_by, amount=amount, currency=group.currency, category=category, note=note, split_method=method, spent_at=datetime.now(), deleted=False))
    db.flush()
    db.add_all([ExpenseShare(expense_id=expense_id, group_id=group_id, member_id=member_id, amount=share) for member_id, share in zip(ordered, shares)])
    db.commit()
    return expense_id


def dashboard_data(db: Session, group_id: str, member_id: str) -> dict:
    balances = group_balances(db, group_id)
    names = dict(db.execute(select(Member.id, Member.name).where(Member.group_id == group_id)).all())
    greedy = greedy_transfers(balances)
    optimized = optimize_transfers(balances)
    return {"balances": balances, "names": names, "greedy": greedy, "optimized": optimized, "member_balance": balances[member_id]}
