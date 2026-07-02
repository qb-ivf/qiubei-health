"""评价 Pydantic 模型（天津监管 2.4.1，S2）。"""
from datetime import datetime

from pydantic import BaseModel, Field


class EvaluationCreate(BaseModel):
    satisfaction: int = Field(ge=1, le=5, description="1 非常不满意 … 5 非常满意")
    scoring: int = Field(ge=0, le=10, description="0-10 分")
    content: str = Field(min_length=1, max_length=300)
    complaints: str | None = Field(default=None, max_length=1024)


class EvaluationOut(BaseModel):
    id: int
    order_id: int
    satisfaction: int
    scoring: int
    content: str
    complaints: str | None = None
    evaluator: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}
