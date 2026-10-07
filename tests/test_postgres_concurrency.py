import os
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Expense, ExpenseShare, Group, Member, Settlement
from app.services import add_expense, group_balances


POSTGRES_TEST_URL = os.getenv("POSTGRES_TEST_URL")


def cleanup_test_groups(db: Session) -> None:
    test_group_ids = list(db.scalars(select(Group.id).where(Group.id.like("TEST-%"))))
    if not test_group_ids:
        return
    db.execute(delete(ExpenseShare).where(ExpenseShare.group_id.in_(test_group_ids)))
    db.execute(delete(Settlement).where(Settlement.group_id.in_(test_group_ids)))
    db.execute(delete(Expense).where(Expense.group_id.in_(test_group_ids)))
    db.execute(delete(Member).where(Member.group_id.in_(test_group_ids)))
    db.execute(delete(Group).where(Group.id.in_(test_group_ids)))
    db.commit()


@pytest.mark.skipif(not POSTGRES_TEST_URL, reason="Set POSTGRES_TEST_URL to run PostgreSQL locking test")
def test_two_concurrent_expenses_keep_balance_invariant():
    engine = create_engine(POSTGRES_TEST_URL, pool_size=4)
    Base.metadata.create_all(engine)
    suffix = uuid4().hex[:12]
    group_id = f"TEST-{suffix}"
    members = [f"TM-{suffix}-{index}" for index in range(3)]
    with Session(engine) as db:
        cleanup_test_groups(db)
        db.add(Group(id=group_id, name="Concurrency test", kind="test", currency="UZS", created_at=date.today()))
        db.flush()
        db.add_all([Member(group_id=group_id, id=member_id, name=member_id, bank="TEST", joined_at=date.today()) for member_id in members])
        db.commit()

    def write(payer: str) -> None:
        with Session(engine) as db:
            add_expense(db, group_id, payer, 101, "test", "parallel", "teng", members)

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(write, members[:2]))
        with Session(engine) as db:
            balances = group_balances(db, group_id)
            assert sum(balances.values()) == 0
            assert len(balances) == 3
    finally:
        with Session(engine) as db:
            cleanup_test_groups(db)
