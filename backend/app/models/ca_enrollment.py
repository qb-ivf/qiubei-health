"""放心签高级证书协议/智能双录记录。

只保存核验元数据，不保存身份证明文、刷脸照片或视频。agreement_url 只有两分钟
有效，但其中带有核验参数，仍使用现有 Fernet 能力加密落库，便于客户端请求重试。
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class CaEnrollment(Base, TimestampMixin):
    __tablename__ = "ca_enrollments"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    subject_type: Mapped[str] = mapped_column(String(16), index=True)  # doctor/staff
    subject_id: Mapped[int] = mapped_column(BigInteger, index=True)
    provider_user_id: Mapped[str] = mapped_column(String(64))
    order_no: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    verify_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    trade_no: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # initiating/pending/succeeded/failed/expired
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    agreement_url_enc: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    face_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
    provider_msg: Mapped[str | None] = mapped_column(String(255), nullable=True)
    live_rate: Mapped[str | None] = mapped_column(String(16), nullable=True)
    similarity: Mapped[str | None] = mapped_column(String(16), nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
