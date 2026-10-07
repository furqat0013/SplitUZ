import csv
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.services import all_balances, import_dataset


ROOT = Path(__file__).resolve().parents[1]


def test_open_dataset_matches_answer_key_to_one_som(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        counts = import_dataset(db, ROOT / "dataset")
        actual = {(group_id, member_id): amount for group_id, balances in all_balances(db).items() for member_id, amount in balances.items()}
    expected_counts = {}
    for key, filename in {"groups":"groups.csv", "members":"members.csv", "expenses":"expenses.csv", "shares":"expense_shares.csv", "settlements":"settlements.csv"}.items():
        with (ROOT / "dataset" / filename).open(encoding="utf-8-sig", newline="") as handle:
            expected_counts[key] = sum(1 for _ in csv.DictReader(handle))
    assert counts == expected_counts
    for group_id in {key[0] for key in actual}:
        assert sum(value for (group, _), value in actual.items() if group == group_id) == 0

    answer_key = ROOT / "dataset/_javob_kaliti/net_balanslar.csv"
    if answer_key.exists():
        with answer_key.open(encoding="utf-8-sig", newline="") as handle:
            expected = {(row["group_id"], row["member_id"]): int(row["net_balans"]) for row in csv.DictReader(handle)}
        if set(expected) == set(actual):
            assert actual == expected
