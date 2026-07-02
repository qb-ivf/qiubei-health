"""电子处方 + 病历（EMR）模型（PRD §3.3/§3.4，M5）。"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Prescription(Base, TimestampMixin):
    __tablename__ = "prescriptions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, index=True)
    doctor_id: Mapped[int] = mapped_column(BigInteger, index=True)
    patient_id: Mapped[int] = mapped_column(BigInteger, index=True)

    # 病历（EMR）
    chief: Mapped[str | None] = mapped_column(Text, nullable=True)            # 主诉
    present_illness: Mapped[str | None] = mapped_column(Text, nullable=True)  # 现病史
    diagnosis: Mapped[str | None] = mapped_column(String(255), nullable=True) # 初步诊断
    advice: Mapped[str | None] = mapped_column(Text, nullable=True)           # 医嘱

    # ICD-10 诊断编码（天津监管必输：mainDiagnoseCode/icdCode；多个用 | 分隔）
    icd_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    icd_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # 处方药品：[{name, spec, qty, usage, price_fen}]
    items: Mapped[list] = mapped_column(JSON, default=list)

    audit_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/approved/rejected
    reject_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ca_sign: Mapped[str | None] = mapped_column(String(255), nullable=True)   # CA 数字签名（M9 接真实）
    pdf_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # —— 天津监管字段（S3）：审方通过时生成/记录 ——
    recipe_unique_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 处方唯一号（对外备查/核销）
    checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)     # 审方时间（→ checkDate）
    audit_staff_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)    # 审方药师（staff.id）
