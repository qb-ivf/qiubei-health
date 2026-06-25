"""订单模型（PRD §2.1：status 建索引，整型枚举映射状态机）。"""
from sqlalchemy import BigInteger, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..constants import OrderStatus
from .base import Base, TimestampMixin


class Order(Base, TimestampMixin):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, default=0)  # 下单账号
    patient_id: Mapped[int] = mapped_column(BigInteger, index=True)
    doctor_id: Mapped[int] = mapped_column(BigInteger, index=True)
    slot_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    room_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)

    status: Mapped[int] = mapped_column(Integer, default=int(OrderStatus.PENDING))
    register_fee_fen: Mapped[int] = mapped_column(Integer, default=0)  # 挂号费(分)
    drug_fee_fen: Mapped[int] = mapped_column(Integer, default=0)      # 药费(分)
    consult_type: Mapped[str] = mapped_column(String(8), default="video")  # video 视频 / text 图文

    __table_args__ = (Index("ix_orders_status", "status"),)
