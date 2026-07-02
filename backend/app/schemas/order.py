"""订单的 Pydantic 校验/序列化模型。"""
from pydantic import BaseModel

from ..constants import OrderStatus


class RegisterOrderCreate(BaseModel):
    doctor_id: int
    slot_id: int
    patient_id: int
    consult_type: str = "video"   # video 视频 / text 图文
    # 复诊合规声明（视频问诊必填，天津监管 referralFlag/originalDiagnosis）
    referral_flag: bool | None = None
    original_diagnosis: str | None = None


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
    room_id: str | None = None   # CONSULTING 时有值，供患者错过呼叫后重进视频房
    order_id: int | None = None


class PrepayOut(BaseModel):
    """微信支付五元组（mock；真实由后端下单返回）。"""
    timeStamp: str
    nonceStr: str
    package: str
    signType: str
    paySign: str
    order_id: int
