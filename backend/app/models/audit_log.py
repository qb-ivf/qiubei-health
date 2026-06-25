"""操作审计日志（PRD §一.操作审计）。

涉及医疗数据/资金/资质的写操作（审方、资质终审、提现、药品、账号）落库留存备查。
"""
from sqlalchemy import BigInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_id: Mapped[int] = mapped_column(BigInteger, index=True, default=0)  # staff.id
    actor_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(16), nullable=True)
    action: Mapped[str] = mapped_column(String(32), index=True)        # 审方通过/驳回处方/资质终审...
    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)  # prescription/doctor/...
    target_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
