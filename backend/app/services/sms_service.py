"""短信验证码服务：腾讯云 SMS 下发、Redis 限频与一次性校验。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time as datetime_time, timedelta, timezone
import hashlib
import hmac
import json
import logging
import re
import secrets
import time
from zoneinfo import ZoneInfo

import httpx

from ..core.config import settings
from ..core.redis import redis_client

logger = logging.getLogger("sms")

SMS_PURPOSE_REGISTER_PHONE = "register_phone"
SMS_PURPOSE_CHANGE_PHONE = "change_phone"
SMS_PURPOSES = frozenset({SMS_PURPOSE_REGISTER_PHONE, SMS_PURPOSE_CHANGE_PHONE})

_PHONE_RE = re.compile(r"^1\d{10}$")
_CODE_KEY = "sms:code:{phone_token}"
_RATE_KEY = "sms:rate:{phone_token}"
_DAILY_KEY = "sms:daily:{phone_token}:{date}"
_USER_HOURLY_KEY = "sms:user-hour:{user_id}"
_IP_HOURLY_KEY = "sms:ip-hour:{ip_token}"
_CHINA_TZ = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class TencentSmsResult:
    ok: bool
    code: str = ""
    request_id: str = ""


def _template_id(purpose: str) -> str:
    if purpose == SMS_PURPOSE_REGISTER_PHONE:
        return settings.TENCENT_SMS_TEMPLATE_REGISTER_PHONE_ID.strip()
    if purpose == SMS_PURPOSE_CHANGE_PHONE:
        return settings.TENCENT_SMS_TEMPLATE_CHANGE_PHONE_ID.strip()
    return ""


def tencent_sms_config_errors(purpose: str | None = None) -> list[str]:
    """返回配置错误项，绝不返回密钥值。"""
    required = {
        "TENCENT_SMS_SECRET_ID": settings.TENCENT_SMS_SECRET_ID,
        "TENCENT_SMS_SECRET_KEY": settings.TENCENT_SMS_SECRET_KEY,
        "TENCENT_SMS_SDK_APP_ID": settings.TENCENT_SMS_SDK_APP_ID,
        "TENCENT_SMS_SIGN": settings.TENCENT_SMS_SIGN,
    }
    errors = [key for key, value in required.items() if not str(value).strip()]
    purposes = [purpose] if purpose else sorted(SMS_PURPOSES)
    for item in purposes:
        if not _template_id(item):
            errors.append(
                "TENCENT_SMS_TEMPLATE_REGISTER_PHONE_ID"
                if item == SMS_PURPOSE_REGISTER_PHONE
                else "TENCENT_SMS_TEMPLATE_CHANGE_PHONE_ID"
            )
    if settings.TENCENT_SMS_CODE_TTL_SECONDS != 300:
        errors.append("TENCENT_SMS_CODE_TTL_SECONDS（当前模板要求 300 秒）")
    return errors


def _tencent_configured(purpose: str) -> bool:
    return not tencent_sms_config_errors(purpose)


def _common_tencent_configured() -> bool:
    return all(
        (
            settings.TENCENT_SMS_SECRET_ID,
            settings.TENCENT_SMS_SECRET_KEY,
            settings.TENCENT_SMS_SDK_APP_ID,
            settings.TENCENT_SMS_SIGN,
        )
    )


def _phone_token(phone: str) -> str:
    """用不可逆令牌作为 Redis 键，避免把手机号直接写入键空间。"""
    return hmac.new(
        settings.JWT_SECRET.encode("utf-8"),
        phone.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:32]


async def _increment_window(key: str, ttl_seconds: int) -> int:
    count = int(await redis_client.incr(key))
    if count == 1:
        await redis_client.expire(key, ttl_seconds)
    return count


async def _check_rate_limit(
    phone: str,
    user_id: int,
    client_ip: str | None,
) -> str | None:
    token = _phone_token(phone)
    interval = max(30, settings.TENCENT_SMS_SEND_INTERVAL_SECONDS)
    acquired = await redis_client.set(
        _RATE_KEY.format(phone_token=token),
        "1",
        ex=interval,
        nx=True,
    )
    if not acquired:
        return f"发送过于频繁，请 {interval} 秒后重试"

    now = datetime.now(_CHINA_TZ)
    tomorrow = datetime.combine(
        now.date() + timedelta(days=1),
        datetime_time.min,
        tzinfo=_CHINA_TZ,
    )
    daily_count = await _increment_window(
        _DAILY_KEY.format(phone_token=token, date=now.strftime("%Y%m%d")),
        max(1, int((tomorrow - now).total_seconds())),
    )
    if daily_count > max(1, settings.TENCENT_SMS_PHONE_DAILY_LIMIT):
        return "该手机号今日发送次数已达上限，请明日再试"

    user_count = await _increment_window(
        _USER_HOURLY_KEY.format(user_id=user_id),
        60 * 60,
    )
    if user_count > max(1, settings.TENCENT_SMS_USER_HOURLY_LIMIT):
        return "当前账号发送次数已达上限，请稍后再试"
    if client_ip:
        ip_count = await _increment_window(
            _IP_HOURLY_KEY.format(ip_token=_phone_token(client_ip)),
            60 * 60,
        )
        if ip_count > max(1, settings.TENCENT_SMS_IP_HOURLY_LIMIT):
            return "当前网络发送次数已达上限，请稍后再试"
    return None


def _template_params(purpose: str, code: str) -> list[str]:
    if purpose == SMS_PURPOSE_REGISTER_PHONE:
        return [code, str(settings.TENCENT_SMS_CODE_TTL_SECONDS // 60)]
    return [code]


async def send_code(
    phone: str,
    purpose: str,
    *,
    user_id: int,
    client_ip: str | None = None,
) -> tuple[bool, str, str | None]:
    """生成并下发验证码；dev_code 只在 DEBUG 且未配置腾讯云时返回。"""
    phone = phone.strip()
    if not _PHONE_RE.fullmatch(phone):
        return False, "手机号格式不正确", None
    if purpose not in SMS_PURPOSES:
        return False, "短信用途不支持", None
    if not _tencent_configured(purpose) and not settings.DEBUG:
        logger.error("生产环境腾讯云短信配置不完整")
        return False, "短信服务暂不可用，请联系管理员", None

    rate_error = await _check_rate_limit(phone, user_id, client_ip)
    if rate_error:
        return False, rate_error, None

    code = f"{secrets.randbelow(1_000_000):06d}"
    if _common_tencent_configured() and _template_id(purpose):
        result = await _send_tencent(phone, code, purpose)
        if not result.ok:
            return False, "短信发送失败，请稍后重试", None
        await redis_client.set(
            _CODE_KEY.format(phone_token=_phone_token(phone)),
            code,
            ex=settings.TENCENT_SMS_CODE_TTL_SECONDS,
        )
        return True, "验证码已发送", None

    await redis_client.set(
        _CODE_KEY.format(phone_token=_phone_token(phone)),
        code,
        ex=settings.TENCENT_SMS_CODE_TTL_SECONDS,
    )
    logger.info("[SMS dev] 已生成验证码（未记录手机号和验证码）")
    return True, "验证码已生成（开发模式）", code


async def verify_code(phone: str, code: str) -> bool:
    """校验验证码，成功后立即失效。"""
    if not phone or not code:
        return False
    key = _CODE_KEY.format(phone_token=_phone_token(phone.strip()))
    saved = await redis_client.get(key)
    if saved is None or not hmac.compare_digest(str(saved), str(code)):
        return False
    await redis_client.delete(key)
    return True


async def _send_tencent(phone: str, code: str, purpose: str) -> TencentSmsResult:
    """调用腾讯云 SendSms（TC3-HMAC-SHA256），日志不记录手机号或验证码。"""
    secret_id = settings.TENCENT_SMS_SECRET_ID
    secret_key = settings.TENCENT_SMS_SECRET_KEY
    host = "sms.tencentcloudapi.com"
    service = "sms"
    action = "SendSms"
    version = "2021-01-11"
    region = settings.TENCENT_SMS_REGION or "ap-guangzhou"
    timestamp = int(time.time())
    date = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")

    payload = json.dumps(
        {
            "PhoneNumberSet": [f"+86{phone}"],
            "SmsSdkAppId": settings.TENCENT_SMS_SDK_APP_ID,
            "SignName": settings.TENCENT_SMS_SIGN,
            "TemplateId": _template_id(purpose),
            "TemplateParamSet": _template_params(purpose, code),
        },
        separators=(",", ":"),
    )

    content_type = "application/json; charset=utf-8"
    canonical_headers = (
        f"content-type:{content_type}\nhost:{host}\nx-tc-action:{action.lower()}\n"
    )
    signed_headers = "content-type;host;x-tc-action"
    hashed_payload = hashlib.sha256(payload.encode()).hexdigest()
    canonical_request = (
        f"POST\n/\n\n{canonical_headers}\n{signed_headers}\n{hashed_payload}"
    )

    scope = f"{date}/{service}/tc3_request"
    hashed_canonical_request = hashlib.sha256(canonical_request.encode()).hexdigest()
    string_to_sign = (
        f"TC3-HMAC-SHA256\n{timestamp}\n{scope}\n{hashed_canonical_request}"
    )

    def _sign(key: bytes, message: str) -> bytes:
        return hmac.new(key, message.encode(), hashlib.sha256).digest()

    secret_date = _sign(("TC3" + secret_key).encode(), date)
    secret_service = _sign(secret_date, service)
    secret_signing = _sign(secret_service, "tc3_request")
    signature = hmac.new(
        secret_signing,
        string_to_sign.encode(),
        hashlib.sha256,
    ).hexdigest()
    authorization = (
        f"TC3-HMAC-SHA256 Credential={secret_id}/{scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    headers = {
        "Authorization": authorization,
        "Content-Type": content_type,
        "Host": host,
        "X-TC-Action": action,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": version,
        "X-TC-Region": region,
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"https://{host}",
                content=payload.encode(),
                headers=headers,
            )
            response.raise_for_status()
            data = response.json().get("Response", {})
        request_id = str(data.get("RequestId", ""))
        status_set = data.get("SendStatusSet") or []
        if status_set and status_set[0].get("Code") == "Ok":
            return TencentSmsResult(True, "Ok", request_id)
        error = data.get("Error") or {}
        provider_code = str(
            error.get("Code")
            or (status_set[0].get("Code") if status_set else "Unknown")
        )
        logger.error(
            "腾讯云短信发送失败 code=%s request_id=%s",
            provider_code,
            request_id,
        )
        return TencentSmsResult(False, provider_code, request_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("腾讯云短信发送异常 type=%s", type(exc).__name__)
        return TencentSmsResult(False, type(exc).__name__)
