"""分账流水（PRD §4.3）。每笔完成订单按比例拆分：医院留存/医生分成/平台服务费。"""
from sqlalchemy import BigInteger, Integer
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Ledger(Base, TimestampMixin):
    __tablename__ = "ledger"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True)
    total_fen: Mapped[int] = mapped_column(Integer, default=0)
    hospital_fen: Mapped[int] = mapped_column(Integer, default=0)
    doctor_fen: Mapped[int] = mapped_column(Integer, default=0)
    platform_fen: Mapped[int] = mapped_column(Integer, default=0)
