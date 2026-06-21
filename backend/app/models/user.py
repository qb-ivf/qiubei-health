"""账号 / 就诊人 / 医生 / 知情同意 模型（M1）。

身份证、手机号以密文落库（*_enc 字段），返回前再脱敏。
"""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    openid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(16), default="patient")  # constants.Role
    phone_enc: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Patient(Base, TimestampMixin):
    """就诊人（实名，支持多就诊人）。"""
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)  # 所属账号
    name: Mapped[str] = mapped_column(String(64))
    id_card_enc: Mapped[str] = mapped_column(String(255))
    gender: Mapped[str | None] = mapped_column(String(8), nullable=True)
    relation: Mapped[str] = mapped_column(String(16), default="本人")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class Doctor(Base, TimestampMixin):
    """医生资质（白名单来源，PRD §2.4 / §4.1）。"""
    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    license_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    practice_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dept: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str | None] = mapped_column(String(32), nullable=True)
    audit_status: Mapped[str] = mapped_column(String(16), default="pending")  # pending/approved/rejected
    register_fee_fen: Mapped[int] = mapped_column(Integer, default=5000)  # 挂号费(分)
    good_at: Mapped[str | None] = mapped_column(String(255), nullable=True)
    years: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Consent(Base, TimestampMixin):
    """知情同意 / 隐私协议签署存证（FRD §2.3 / PRD §2.5）。"""
    __tablename__ = "consents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    consent_type: Mapped[str] = mapped_column(String(32), default="diagnosis")
    version: Mapped[str] = mapped_column(String(16), default="v1")
    signed_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
