"""订单的 Pydantic 校验/序列化模型。"""
from pydantic import BaseModel

from ..constants import OrderStatus


class RegisterOrderCreate(BaseModel):
    doctor_id: int
    slot_id: int
    patient_id: int


class OrderOut(BaseModel):
    id: int
    order_no: str
    status: OrderStatus
    register_fee_fen: int
    drug_fee_fen: int

    model_config = {"from_attributes": True}


class ActiveOrderOut(BaseModel):
    has: bool
    status: OrderStatus | None = None
    doctor_name: str | None = None


class PrepayOut(BaseModel):
    """微信支付五元组（mock；真实由后端下单返回）。"""
    timeStamp: str
    nonceStr: str
    package: str
    signType: str
    paySign: str
    order_id: int


class PayCallback(BaseModel):
    order_no: str
    # 真实环境：含微信支付 V3 回调密文，需验签后解密
