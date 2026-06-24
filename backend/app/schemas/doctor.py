"""医生 / 号源 Pydantic 模型（M2）。"""
from pydantic import BaseModel


class DoctorOut(BaseModel):
    id: int
    name: str | None = None
    dept: str | None = None
    title: str | None = None
    good_at: str | None = None
    years: int | None = None
    register_fee_fen: int

    model_config = {"from_attributes": True}


class SlotOut(BaseModel):
    id: int
    day: str
    start_time: str
    end_time: str
    remaining: int


class QualificationIn(BaseModel):
    """医生资质提交（执业认证）。"""
    name: str
    license_no: str            # 医师资格证编号
    practice_no: str           # 医师执业证编号
    dept: str | None = None
    title: str | None = None
    good_at: str | None = None
    years: int | None = None


class DoctorProfileOut(BaseModel):
    """医生本人档案（含审核状态，供医生端按状态路由）。"""
    id: int
    name: str | None = None
    dept: str | None = None
    title: str | None = None
    license_no: str | None = None
    practice_no: str | None = None
    good_at: str | None = None
    years: int | None = None
    audit_status: str          # pending / approved / rejected

    model_config = {"from_attributes": True}
