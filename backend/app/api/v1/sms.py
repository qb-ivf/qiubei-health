"""短信验证码接口。"""
from ipaddress import ip_address
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from ..deps import get_current_user_id
from ...services import sms_service

router = APIRouter(prefix="/sms", tags=["sms"])


class SendCodeBody(BaseModel):
    phone: str
    # 兼容已发布但尚未携带 purpose 的旧患者端；新版本会显式区分两类模板。
    purpose: Literal["register_phone", "change_phone"] = "register_phone"


def _valid_ip(value: str | None) -> str | None:
    try:
        return str(ip_address((value or "").strip()))
    except ValueError:
        return None


def _client_ip(request: Request) -> str | None:
    direct = _valid_ip(request.client.host) if request.client else None
    if direct and (ip_address(direct).is_private or ip_address(direct).is_loopback):
        # 只信任来自本机/容器私网 Nginx 的标准转发头，避免公网客户端伪造 IP。
        real_ip = _valid_ip(request.headers.get("x-real-ip", ""))
        if real_ip:
            return real_ip
        forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0]
        forwarded_ip = _valid_ip(forwarded)
        if forwarded_ip:
            return forwarded_ip
    return direct


@router.post("/send-code")
async def send_code(
    body: SendCodeBody,
    request: Request,
    user_id: int = Depends(get_current_user_id),
):
    """下发验证码到手机号（限频 60s）。开发模式返回 dev_code 便于联调。"""
    ok, msg, dev_code = await sms_service.send_code(
        body.phone,
        body.purpose,
        user_id=user_id,
        client_ip=_client_ip(request),
    )
    if not ok:
        limited = "频繁" in msg or "上限" in msg
        raise HTTPException(status_code=429 if limited else 400, detail=msg)
    return {"ok": True, "msg": msg, "dev_code": dev_code}
