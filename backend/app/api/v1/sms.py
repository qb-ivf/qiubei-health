"""短信验证码接口。"""
from fastapi import APIRouter, Body, HTTPException

from ...services import sms_service

router = APIRouter(prefix="/sms", tags=["sms"])


@router.post("/send-code")
async def send_code(phone: str = Body(embed=True)):
    """下发验证码到手机号（限频 60s）。开发模式返回 dev_code 便于联调。"""
    ok, msg, dev_code = await sms_service.send_code(phone)
    if not ok:
        raise HTTPException(status_code=429 if "频繁" in msg else 400, detail=msg)
    return {"ok": True, "msg": msg, "dev_code": dev_code}
