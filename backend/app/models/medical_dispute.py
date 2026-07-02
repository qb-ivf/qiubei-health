"""医疗争议 / 不良事件记录（天津监管 2.4.2 pushMedicalDispute 数据源，S2）。

规范要求每日签到：当日无事件也需以空数组调用一次接口（S3 采集器负责）。
合规记录只增改不删。
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class MedicalDispute(Base, TimestampMixin):
    __tablename__ = "medical_disputes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int | None] = mapped_column(BigInteger, index=True, nullable=True)  # 关联订单（可空）
    business_type: Mapped[str] = mapped_column(String(6), default="4")  # 1图文咨询 4在线复诊 5在线处方 99其他
    patient_name: Mapped[str] = mapped_column(String(50))
    mobile: Mapped[str] = mapped_column(String(15))
    event_description: Mapped[str] = mapped_column(String(1024))   # 事件描述
    event_date: Mapped[datetime] = mapped_column(DateTime)         # 事件发生时间
    event_reason: Mapped[str] = mapped_column(String(1024))        # 发生的主要原因
    take_steps: Mapped[str] = mapped_column(String(1024))          # 采取的措施
    damage_degree: Mapped[str] = mapped_column(String(1024))       # 患者损害程度描述
    improvements: Mapped[str] = mapped_column(String(1024))        # 后续改进措施
    report_dept: Mapped[str] = mapped_column(String(30))           # 上报科室
    report_person: Mapped[str] = mapped_column(String(50))         # 上报人
    report_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # 事件上报时间（默认=登记时间）
