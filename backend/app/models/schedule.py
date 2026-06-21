"""排班号源（PRD §3.1）。号源扣减以 Redis 为准（防超卖），DB 存初始配额。"""
from sqlalchemy import BigInteger, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Slot(Base, TimestampMixin):
    __tablename__ = "slots"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    doctor_id: Mapped[int] = mapped_column(BigInteger, index=True)
    day: Mapped[str] = mapped_column(String(10))        # 2026-06-22
    start_time: Mapped[str] = mapped_column(String(5))  # 09:00
    end_time: Mapped[str] = mapped_column(String(5))    # 09:30
    quota: Mapped[int] = mapped_column(Integer, default=5)
    remaining: Mapped[int] = mapped_column(Integer, default=5)

    __table_args__ = (Index("ix_slots_doctor_day", "doctor_id", "day"),)
