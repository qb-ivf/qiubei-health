"""RTC 音视频接口（PRD §2.3 / M4）：服务端动态下发入房参数（UserSig）。"""
from fastapi import APIRouter, Depends, Header, HTTPException

from ...core.config import settings
from ...core.security import decode_token
from ...services import trtc

router = APIRouter(prefix="/rtc", tags=["rtc"])


def _current_user(authorization: str = Header(default="")) -> dict:
    payload = decode_token(authorization.replace("Bearer ", "").strip())
    if not payload:
        raise HTTPException(status_code=401, detail="未登录或登录态失效")
    return payload


@router.get("/user-sig")
async def user_sig(room_id: str, user=Depends(_current_user)):
    """返回前端 TRTC SDK 入房所需参数。

    UserSig 用官方算法生成（见 services/trtc.py）；配置 TRTC_SDKAPPID/SECRETKEY
    且小程序通过"实时音视频"类目审核后即可真实入房。
    """
    if not settings.TRTC_SDKAPPID or not settings.TRTC_SECRETKEY:
        # 未配置（开发期）：返回占位，前端走视频占位画面
        return {"configured": False, "roomId": room_id, "userId": str(user["sub"])}

    user_id = str(user["sub"])
    return {
        "configured": True,
        "sdkAppId": settings.TRTC_SDKAPPID,
        "userId": user_id,
        "userSig": trtc.gen_user_sig(user_id),
        "roomId": room_id,
        "expire": settings.TRTC_SIG_EXPIRE,
    }
