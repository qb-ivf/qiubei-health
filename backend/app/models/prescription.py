"""电子处方 + 病历（EMR）模型（PRD §3.3/§3.4，M5）。"""
from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, Text
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

    # not_required 表示本次只有电子病历、未开药，不进入药师审方或处方签章。
    audit_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/approved/rejected/not_required
    reject_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # ca_sign 保存放心签真实签署 tradeNo；pdf_url 保存受保护存储中的相对文件名。
    ca_sign: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pdf_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ca_sign_status: Mapped[str | None] = mapped_column(String(16), nullable=True)  # verified/failed
    ca_verify_trade_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ca_source_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ca_file_digest: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ca_signature_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ca_signed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # 仅保存脱敏后的证书元数据；不得保存 idNo、sealDate 或 signatureDegist。
    ca_verify_report: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # 高级证书双录只是签署前的身份/意愿凭据，不等同于 PDF 文档数字签名。
    doctor_ca_order_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pharmacist_ca_order_no: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # —— 天津监管字段（S3）：审方通过时生成/记录 ——
    recipe_unique_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # 处方唯一号（对外备查/核销）
    checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)     # 审方时间（→ checkDate）
    audit_staff_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)    # 审方药师（staff.id）
