import csv
import shutil
from pathlib import Path

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Group
from app.services import import_dataset


ROOT = Path(__file__).resolve().parents[1]


def dataset_copy(tmp_path: Path) -> Path:
    target = tmp_path / "dataset"
    shutil.copytree(ROOT / "dataset", target)
    return target


def rewrite_first(path: Path, change) -> None:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        rows = list(reader)
    change(rows[0])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def assert_rejected_atomically(tmp_path: Path, mutate, message: str) -> None:
    dataset = dataset_copy(tmp_path)
    engine = create_engine(f"sqlite:///{tmp_path / 'validation.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        import_dataset(db, ROOT / "dataset")
        mutate(dataset)
        with pytest.raises(ValueError, match=message):
            import_dataset(db, dataset)
        db.rollback()
        assert db.scalar(select(func.count()).select_from(Group)) == 81


def test_cross_group_share_is_rejected_without_replacing_data(tmp_path):
    def mutate(dataset):
        rewrite_first(dataset / "expense_shares.csv", lambda row: row.update(group_id="G0002", member_id="U000007"))
    assert_rejected_atomically(tmp_path, mutate, "Share group does not match expense group")


def test_negative_share_is_rejected(tmp_path):
    def mutate(dataset):
        path = dataset / "expense_shares.csv"
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle); fields = reader.fieldnames; rows = list(reader)
        rows[0]["ulush"] = "-1"
        rows[1]["ulush"] = str(int(rows[1]["ulush"]) + 1)
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n"); writer.writeheader(); writer.writerows(rows)
    assert_rejected_atomically(tmp_path, mutate, "non-negative BIGINT")


def test_duplicate_settlement_id_is_rejected(tmp_path):
    def mutate(dataset):
        path = dataset / "settlements.csv"
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle); fields = reader.fieldnames; rows = list(reader)
        rows[1]["settlement_id"] = rows[0]["settlement_id"]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n"); writer.writeheader(); writer.writerows(rows)
    assert_rejected_atomically(tmp_path, mutate, "Duplicate settlement_id")


@pytest.mark.parametrize("field,value,message", [
    ("bolish_usuli", "mystery", "Unknown split method"),
    ("valyuta", "USD", "Currency mismatch"),
])
def test_expense_semantics_are_validated(tmp_path, field, value, message):
    def mutate(dataset):
        rewrite_first(dataset / "expenses.csv", lambda row: row.update({field: value}))
    assert_rejected_atomically(tmp_path, mutate, message)
