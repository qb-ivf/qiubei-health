"""处方 Pydantic 模型（M5）。"""
from datetime import datetime

from pydantic import BaseModel


class DrugItem(BaseModel):
    name: str
    spec: str | None = None
    qty: int = 1
    usage: str | None = None
    price_fen: int = 0
    # —— 天津监管处方明细字段（S3，医生端开方表单回传）——
    drug_id: int | None = None        # 药品字典 id（→ drcode）
    frequency: str | None = None      # 使用频度，如 每日3次
    dosage: str | None = None         # 每次剂量，如 1
    drunit: str | None = None         # 剂量单位，如 粒
    dose_unit: str | None = None      # 总量单位，如 盒
    use_days: int | None = None       # 用药天数


class PrescriptionCreate(BaseModel):
    order_id: int
    chief: str | None = None
    present_illness: str | None = None
    diagnosis: str
    advice: str | None = None
    items: list[DrugItem] = []
    # ICD-10 编码（医生端诊断选择器回传；多个用 | 分隔，与监管上报格式一致）
    icd_code: str | None = None
    icd_name: str | None = None


class PrescriptionOut(BaseModel):
    id: int
    order_id: int
    diagnosis: str | None = None
    icd_code: str | None = None
    icd_name: str | None = None
    chief: str | None = None
    advice: str | None = None
    items: list = []
    audit_status: str
    reject_reason: str | None = None
    ca_sign: str | None = None
    doctor_name: str | None = None
    patient_name: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class RejectIn(BaseModel):
    reason: str
