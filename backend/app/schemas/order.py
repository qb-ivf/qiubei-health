"""订单的 Pydantic 校验/序列化模型。"""
from pydantic import BaseModel

from ..constants import OrderStatus


class OrderCreate(BaseModel):
    patient_id: int
    doctor_id: int
    register_fee_fen: int


class OrderOut(BaseModel):
    id: int
    order_no: str
    status: OrderStatus
    register_fee_fen: int
    drug_fee_fen: int

    model_config = {"from_attributes": True}


class PayCallback(BaseModel):
    order_no: str
    # 真实环境：含微信支付 V3 回调密文，需验签后解密
