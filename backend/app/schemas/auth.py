"""鉴权相关 Pydantic 模型（M1）。"""
from pydantic import BaseModel


class WxLogin(BaseModel):
    code: str                      # wx.login 返回的临时登录凭证
    phone_code: str | None = None  # getPhoneNumber 返回的加密码（生产解码取手机号）
    dev_phone: str | None = None   # 开发期直接传手机号（无微信密钥时用）


class AdminLogin(BaseModel):
    username: str
    password: str = ""
    role: str = "pharmacist"  # pharmacist / admin / finance


class TokenOut(BaseModel):
    token: str
    role: str
    user_id: int


class Me(BaseModel):
    id: int
    role: str
    phone: str | None = None  # 脱敏
