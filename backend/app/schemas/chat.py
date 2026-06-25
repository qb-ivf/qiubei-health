"""图文咨询消息 Pydantic 模型。"""
from pydantic import BaseModel


class MessageIn(BaseModel):
    type: str = "text"   # text / image
    content: str


class MessageOut(BaseModel):
    id: int
    sender_role: str     # patient / doctor
    type: str
    content: str

    model_config = {"from_attributes": True}
