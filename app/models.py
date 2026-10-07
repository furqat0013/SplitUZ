from datetime import date, datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKeyConstraint, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Group(Base):
    __tablename__ = "groups"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(64))
    currency: Mapped[str] = mapped_column(String(8), default="UZS")
    created_at: Mapped[date] = mapped_column(Date)
    members: Mapped[list["Member"]] = relationship(back_populates="group", cascade="all, delete-orphan")


class Member(Base):
    __tablename__ = "members"
    group_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    bank: Mapped[str] = mapped_column(String(64))
    joined_at: Mapped[date] = mapped_column(Date)
    __table_args__ = (ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),)
    group: Mapped[Group] = relationship(back_populates="members")


class Expense(Base):
    __tablename__ = "expenses"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    group_id: Mapped[str] = mapped_column(String(64), index=True)
    paid_by: Mapped[str] = mapped_column(String(64))
    amount: Mapped[int] = mapped_column(BigInteger)
    currency: Mapped[str] = mapped_column(String(8))
    category: Mapped[str] = mapped_column(String(100))
    note: Mapped[str] = mapped_column(String(500))
    split_method: Mapped[str] = mapped_column(String(20))
    spent_at: Mapped[datetime] = mapped_column(DateTime)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (
        UniqueConstraint("id", "group_id", name="uq_expense_id_group"),
        CheckConstraint("amount > 0", name="ck_expense_amount_positive"),
        CheckConstraint("split_method IN ('teng','foiz','aniq','pozitsiya')", name="ck_expense_split_method"),
        ForeignKeyConstraint(["group_id"], ["groups.id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["group_id", "paid_by"], ["members.group_id", "members.id"]),
    )


class ExpenseShare(Base):
    __tablename__ = "expense_shares"
    expense_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    group_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    member_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_share_amount_nonnegative"),
        ForeignKeyConstraint(["expense_id", "group_id"], ["expenses.id", "expenses.group_id"], ondelete="CASCADE"),
        ForeignKeyConstraint(["group_id", "member_id"], ["members.group_id", "members.id"]),
        Index("ix_shares_group_member", "group_id", "member_id"),
    )


class Settlement(Base):
    __tablename__ = "settlements"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    group_id: Mapped[str] = mapped_column(String(64), index=True)
    sender_id: Mapped[str] = mapped_column(String(64))
    receiver_id: Mapped[str] = mapped_column(String(64))
    amount: Mapped[int] = mapped_column(BigInteger)
    settled_at: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(32))
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_settlement_amount_positive"),
        CheckConstraint("sender_id <> receiver_id", name="ck_settlement_distinct_members"),
        ForeignKeyConstraint(["group_id", "sender_id"], ["members.group_id", "members.id"]),
        ForeignKeyConstraint(["group_id", "receiver_id"], ["members.group_id", "members.id"]),
    )
