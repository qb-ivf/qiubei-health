"""就诊人 Pydantic 模型（M1）。"""
from pydantic import BaseModel


class PatientCreate(BaseModel):
    name: str
    id_card: str
    gender: str | None = None
    relation: str = "本人"
    phone: str | None = None
    code: str | None = None     # 手机号验证码


class PatientUpdate(BaseModel):
    name: str | None = None
    gender: str | None = None
    relation: str | None = None
    phone: str | None = None
    code: str | None = None     # 改手机号时需验证码


class PatientOut(BaseModel):
    id: int
    name: str          # 脱敏后
    id_card: str       # 脱敏后
    phone: str | None = None  # 脱敏后
    gender: str | None = None
    relation: str
    verified: bool
    is_default: bool


class ConsentIn(BaseModel):
    consent_type: str = "diagnosis"
    version: str = "v1"
