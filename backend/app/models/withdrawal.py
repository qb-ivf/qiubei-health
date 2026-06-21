"""医生提现单（PRD §4.3 提现状态机）。"""
from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Withdrawal(Base, TimestampMixin):
    __tablename__ = "withdrawals"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    doctor_uid: Mapped[int] = mapped_column(BigInteger, index=True)
    doctor_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    amount_fen: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/paid/rejected
