"""腾讯云 TRTC UserSig 生成（官方 TLSSigAPIv2 算法，M4）。

密钥仅存服务端（PRD §2.3）。配置 TRTC_SDKAPPID / TRTC_SECRETKEY 后即可签发
真实可用的 UserSig；类目审核通过后前端 TRTC SDK 组件用它入房。
"""
import base64
import hashlib
import hmac
import json
import time
import zlib

from ..core.config import settings


def _hmacsha256(sdkappid: int, key: str, identifier: str, curr: int, expire: int) -> str:
    raw = (
        f"TLS.identifier:{identifier}\n"
        f"TLS.sdkappid:{sdkappid}\n"
        f"TLS.time:{curr}\n"
        f"TLS.expire:{expire}\n"
    )
    digest = hmac.new(key.encode("utf-8"), raw.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def gen_user_sig(identifier: str, expire: int | None = None) -> str:
    """生成 TRTC UserSig（标准 base64 后做 +/=→*-_ 替换）。"""
    sdkappid = settings.TRTC_SDKAPPID
    key = settings.TRTC_SECRETKEY
    expire = expire or settings.TRTC_SIG_EXPIRE
    curr = int(time.time())

    sig = _hmacsha256(sdkappid, key, identifier, curr, expire)
    doc = {
        "TLS.ver": "2.0",
        "TLS.identifier": str(identifier),
        "TLS.sdkappid": int(sdkappid),
        "TLS.expire": int(expire),
        "TLS.time": int(curr),
        "TLS.sig": sig,
    }
    compressed = zlib.compress(json.dumps(doc).encode("utf-8"))
    return base64.b64encode(compressed).decode("utf-8").translate(str.maketrans("+/=", "*-_"))
