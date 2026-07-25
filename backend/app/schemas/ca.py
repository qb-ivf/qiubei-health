"""放心签高级证书协议/智能双录接口模型。"""
from datetime import datetime

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
