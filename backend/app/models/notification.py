"""站内消息 / 通知（M7，消息诊室 + 通知中心）。"""
from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    ntype: Mapped[str] = mapped_column(String(32), default="system")  # system/order/rx/logistics/refund
    title: Mapped[str] = mapped_column(String(64))
    body: Mapped[str] = mapped_column(String(255), default="")
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    order_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
