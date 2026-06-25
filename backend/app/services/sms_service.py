"""短信验证码服务：腾讯云 SMS 下发 + Redis 校验。

未配置腾讯云凭据时回退开发模式（验证码打印到日志，不真正发短信），便于联调。
配置后（见 config.TENCENT_SMS_*）自动走真实短信。
"""
import hashlib
import hmac
import json
import logging
import random
import time
from datetime import datetime, timezone

import httpx

from ..core.config import settings
from ..core.redis import redis_client

logger = logging.getLogger("sms")

_CODE_KEY = "sms:code:{}"      # 验证码（5 分钟）
_RATE_KEY = "sms:sent:{}"      # 限频（60 秒一条）


def _tencent_configured() -> bool:
    return bool(
        settings.TENCENT_SMS_SECRET_ID and settings.TENCENT_SMS_SECRET_KEY
        and settings.TENCENT_SMS_SDK_APP_ID and settings.TENCENT_SMS_SIGN
        and settings.TENCENT_SMS_TEMPLATE_ID
    )


async def send_code(phone: str) -> tuple[bool, str, str | None]:
    """生成并下发验证码。返回 (是否成功, 提示, dev_code)。dev_code 仅开发模式返回。"""
    if not phone or not phone.isdigit() or len(phone) != 11:
        return False, "手机号格式不正确", None
    if await redis_client.get(_RATE_KEY.format(phone)):
        return False, "发送过于频繁，请稍后再试", None
    code = f"{random.randint(0, 999999):06d}"
    await redis_client.set(_CODE_KEY.format(phone), code, ex=300)
    await redis_client.set(_RATE_KEY.format(phone), "1", ex=60)

    if _tencent_configured():
        ok = await _send_tencent(phone, code)
        return (True, "已发送", None) if ok else (False, "短信发送失败", None)
    logger.warning("[SMS dev] 手机号 %s 验证码=%s（未配腾讯云短信，开发模式不真发）", phone, code)
    return True, "已发送(开发模式)", code  # 开发模式回传验证码，前端自动填


async def verify_code(phone: str, code: str) -> bool:
    if not phone or not code:
        return False
    saved = await redis_client.get(_CODE_KEY.format(phone))
    if saved and saved == code:
        await redis_client.delete(_CODE_KEY.format(phone))
        return True
    return False


async def _send_tencent(phone: str, code: str) -> bool:
    """腾讯云短信 SendSms（TC3-HMAC-SHA256 签名）。"""
    secret_id = settings.TENCENT_SMS_SECRET_ID
    secret_key = settings.TENCENT_SMS_SECRET_KEY
    host = "sms.tencentcloudapi.com"
    service = "sms"
    action = "SendSms"
    version = "2021-01-11"
    region = settings.TENCENT_SMS_REGION or "ap-guangzhou"
    ts = int(time.time())
    date = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")

    payload = json.dumps({
        "PhoneNumberSet": ["+86" + phone],
        "SmsSdkAppId": settings.TENCENT_SMS_SDK_APP_ID,
        "SignName": settings.TENCENT_SMS_SIGN,
        "TemplateId": settings.TENCENT_SMS_TEMPLATE_ID,
        "TemplateParamSet": [code],
    }, separators=(",", ":"))

    ct = "application/json; charset=utf-8"
    canonical_headers = f"content-type:{ct}\nhost:{host}\nx-tc-action:{action.lower()}\n"
    signed_headers = "content-type;host;x-tc-action"
    hashed_payload = hashlib.sha256(payload.encode()).hexdigest()
    canonical_request = f"POST\n/\n\n{canonical_headers}\n{signed_headers}\n{hashed_payload}"

    scope = f"{date}/{service}/tc3_request"
    hashed_canon = hashlib.sha256(canonical_request.encode()).hexdigest()
    string_to_sign = f"TC3-HMAC-SHA256\n{ts}\n{scope}\n{hashed_canon}"

    def _h(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode(), hashlib.sha256).digest()

    secret_date = _h(("TC3" + secret_key).encode(), date)
    secret_service = _h(secret_date, service)
    secret_signing = _h(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
    authorization = (
        f"TC3-HMAC-SHA256 Credential={secret_id}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    headers = {
        "Authorization": authorization, "Content-Type": ct, "Host": host,
        "X-TC-Action": action, "X-TC-Timestamp": str(ts), "X-TC-Version": version, "X-TC-Region": region,
    }
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.post(f"https://{host}", content=payload.encode(), headers=headers)
            data = r.json()
        item = (data.get("Response", {}).get("SendStatusSet") or [{}])[0]
        if item.get("Code") == "Ok":
            return True
        logger.warning("腾讯云短信发送失败: %s", data)
        return False
    except Exception as e:  # noqa: BLE001
        logger.warning("腾讯云短信请求异常: %s", e)
        return False
