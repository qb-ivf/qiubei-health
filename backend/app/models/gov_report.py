"""卫健委监管上报任务（PRD §5.1）。异步队列 + 重试 + 死信。"""
from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class GovReport(Base, TimestampMixin):
    __tablename__ = "gov_reports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    biz_type: Mapped[str] = mapped_column(String(32))   # consultation / prescription
    biz_id: Mapped[int] = mapped_column(BigInteger, index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/success/failed/dead
    retries: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
