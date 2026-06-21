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
