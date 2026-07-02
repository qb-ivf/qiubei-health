"""监管上报任务队列（天津监管 S3，docs/tianjin_supervision_plan.md）。

一行 = 一次对监管平台某方法的调用任务：payload 在入队时快照（保证重报数据一致、可审计），
worker 只负责发送。幂等以 (biz_type, biz_id) 为键，由 compliance_service.enqueue 在应用层保证。
"""
from datetime import date, datetime

from sqlalchemy import JSON, BigInteger, Date, DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class GovReport(Base, TimestampMixin):
    __tablename__ = "gov_reports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    biz_type: Mapped[str] = mapped_column(String(32))   # consult/referral/emr/recipe/verification/evaluation/dispute_signin/drug
    biz_id: Mapped[int] = mapped_column(BigInteger, index=True)
    method: Mapped[str | None] = mapped_column(String(64), nullable=True)   # X-Service-Method
    payload: Mapped[list | None] = mapped_column(JSON, nullable=True)       # 入队时快照（数组）
    batch_date: Mapped[date | None] = mapped_column(Date, nullable=True)    # 所属批次（北京时间日期）
    status: Mapped[str] = mapped_column(String(16), default="pending")      # pending/success/failed/dead
    retries: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 退避重试时间（UTC）
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    msg_code: Mapped[int | None] = mapped_column(Integer, nullable=True)    # 平台业务返回码
    resp_msg: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 平台返回文案
    last_error: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (Index("ix_gov_reports_biz", "biz_type", "biz_id"),)
