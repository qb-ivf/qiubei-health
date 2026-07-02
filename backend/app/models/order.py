"""订单模型（PRD §2.1：status 建索引，整型枚举映射状态机）。"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Index, Integer, String
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

    # —— 业务时间戳 / 支付流水（天津监管上报字段来源，docs/tianjin_supervision_plan.md §4.2） ——
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)      # 挂号费支付时间
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 医生接诊时间（→ startDate）
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 问诊结束时间（→ endDate）
    cancel_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)   # 取消/退款原因（→ refuseReason）
    wx_transaction_id: Mapped[str | None] = mapped_column(String(64), nullable=True)       # 挂号费微信流水号
    wx_drug_transaction_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 药费微信流水号（→ 核销 tradeNo）

    # —— 复诊合规（互联网医院只允许复诊；→ referralFlag / originalDiagnosis / firstDiagnosis） ——
    referral_flag: Mapped[bool | None] = mapped_column(Boolean, nullable=True)          # 患者复诊声明
    original_diagnosis: Mapped[str | None] = mapped_column(String(255), nullable=True)  # 实体医院原诊断
    first_diagnosis_file_ids: Mapped[str | None] = mapped_column(String(300), nullable=True)  # 首诊材料监管附件id（逗号分隔）

    __table_args__ = (Index("ix_orders_status", "status"),)
