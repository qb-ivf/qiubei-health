"""放心签高级证书协议/智能双录接口模型。"""
from datetime import date, datetime

from pydantic import BaseModel, Field


class CaEnrollmentOut(BaseModel):
    order_no: str
    verify_id: str | None = None
    status: str
    face_code: str | None = None
    provider_msg: str | None = None
    live_rate: str | None = None
    similarity: str | None = None
    occurred_at: datetime | None = None
    last_checked_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class CaEnrollmentStartOut(CaEnrollmentOut):
    agreement_url: str | None = None
    expires_in_seconds: int = 120


class CaConfigOut(BaseModel):
    enabled: bool
    document_sign_enabled: bool
    required: bool
    ready: bool
    errors: list[str] = Field(default_factory=list)
    service_expires_on: date | None = None
    personal_cert_expires_on: date | None = None
    effective_expires_on: date | None = None
    days_until_expiry: int | None = None
    expiry_warning: str | None = None
    expiry_expired: bool = False


class CaAdminProgressOut(BaseModel):
    total: int = 0
    record_ready: int = 0
    succeeded: int = 0
    pending: int = 0
    failed: int = 0
    expired: int = 0
    not_started: int = 0


class CaAdminSubjectOut(BaseModel):
    subject_type: str
    subject_id: int
    name: str
    account_status: str
    record_ready: bool
    ca_status: str
    face_code: str | None = None
    completed_at: datetime | None = None
    last_checked_at: datetime | None = None


class CaAdminOverviewOut(BaseModel):
    doctors: CaAdminProgressOut
    pharmacists: CaAdminProgressOut
    subjects: list[CaAdminSubjectOut] = Field(default_factory=list)
    effective_expires_on: date | None = None
    expiry_warning: str | None = None
    expiry_expired: bool = False
    generated_at: datetime
