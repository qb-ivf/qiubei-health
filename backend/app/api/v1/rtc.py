"""RTC 音视频 UserSig 计算（PRD §2.3：密钥仅存服务端，动态下发）。"""
import base64
import hashlib
import hmac
import time

from fastapi import APIRouter, Depends

from ...core.config import settings
from ...core.security import decode_token
from fastapi import Header, HTTPException

router = APIRouter(prefix="/rtc", tags=["rtc"])


def _current_user(authorization: str = Header(default="")) -> dict:
    token = authorization.replace("Bearer ", "")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="未登录或登录态失效")
    return payload


@router.get("/user-sig")
async def user_sig(room_id: str, user=Depends(_current_user)):
    """返回 TRTC UserSig（有效期 120 分钟）。

    注：此处给出 HMAC-SHA256 骨架，正式接入需替换为腾讯云官方 UserSig
    生成算法（含 zlib 压缩 + base64），SDKAppID / SecretKey 来自 settings。
    """
    user_id = str(user["sub"])
    expire = settings.TRTC_SIG_EXPIRE
    ts = int(time.time())
    raw = f"{settings.TRTC_SDKAPPID}{user_id}{room_id}{ts}{expire}"
    sig = hmac.new(settings.TRTC_SECRETKEY.encode(), raw.encode(), hashlib.sha256).digest()
    return {
        "sdkAppId": settings.TRTC_SDKAPPID,
        "userId": user_id,
        "roomId": room_id,
        "userSig": base64.b64encode(sig).decode(),
        "expire": expire,
    }
