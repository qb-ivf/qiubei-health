"""图文咨询消息（订单内，文字/图片）。"""
from sqlalchemy import BigInteger, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True)
    sender_role: Mapped[str] = mapped_column(String(8))   # patient / doctor
    type: Mapped[str] = mapped_column(String(8), default="text")  # text / image
    content: Mapped[str] = mapped_column(String(1024))    # 文本内容 或 图片 URL

    __table_args__ = (Index("ix_messages_order", "order_id"),)
