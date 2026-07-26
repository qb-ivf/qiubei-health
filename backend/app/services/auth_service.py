"""鉴权服务（M1）：微信登录 → 用户 → JWT；医生白名单。"""
import hashlib
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import Role
from ..core.config import settings
from ..core.crypto import encrypt
from ..core.redis import redis_client
from ..core.security import create_token
from ..models.user import Doctor, User

logger = logging.getLogger("auth")


async def _wx_access_token(appid: str, secret: str) -> str | None:
    """获取并缓存小程序 access_token（有效 ~7200s）。"""
    key = f"wx:access_token:{appid}"
    cached = await redis_client.get(key)
    if cached:
        return cached
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                "https://api.weixin.qq.com/cgi-bin/token",
                params={"grant_type": "client_credential", "appid": appid, "secret": secret},
            )
            data = r.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("获取微信 access_token 请求失败: %s", type(exc).__name__)
        return None
    token = data.get("access_token")
    if token:
        await redis_client.set(key, token, ex=max(int(data.get("expires_in", 7200)) - 200, 60))
        return token
    logger.warning("获取 access_token 失败: %s", data)
    return None


async def wx_get_phone(phone_code: str, appid: str, secret: str) -> str | None:
    """用 getPhoneNumber 返回的 code 换取手机号（新版动态码方案）。"""
    token = await _wx_access_token(appid, secret)
    if not token:
        return None
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.post(
                f"https://api.weixin.qq.com/wxa/business/getuserphonenumber?access_token={token}",
                json={"code": phone_code},
            )
            data = r.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("微信手机号解密请求失败: %s", type(exc).__name__)
        return None
    if data.get("errcode") == 0 and data.get("phone_info"):
        return data["phone_info"].get("purePhoneNumber")
    logger.warning("getuserphonenumber 失败: %s", data)
    return None


async def _resolve_phone(phone_code: str | None, dev_phone: str | None, appid: str, secret: str) -> str | None:
    """优先用 getPhoneNumber 真实解密；dev_phone 仅 DEBUG 本地联调可用。"""
    if phone_code and appid and secret:
        phone = await wx_get_phone(phone_code, appid, secret)
        if phone:
            return phone
    return dev_phone if settings.DEBUG else None


async def wx_code2session(code: str, appid: str, secret: str) -> str | None:
    """用 code 换 openid；伪 openid 仅 DEBUG 本地联调可用。"""
    if not appid or not secret:
        if settings.DEBUG:
            return "dev_" + hashlib.sha256(code.encode()).hexdigest()[:24]
        logger.error("生产环境微信登录凭据未配置")
        return None
    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {"appid": appid, "secret": secret, "js_code": code, "grant_type": "authorization_code"}
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(url, params=params)
            data = r.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("微信 code2session 请求失败: %s", type(exc).__name__)
        return None
    if "openid" not in data:
        logger.warning("code2session 失败: %s", data)
        return None
    return data["openid"]


async def _get_or_create_user(db: AsyncSession, openid: str, role: str, phone: str | None) -> User:
    res = await db.execute(select(User).where(User.openid == openid))
    user = res.scalar_one_or_none()
    if user is None:
        user = User(openid=openid, role=role, phone_enc=encrypt(phone))
        db.add(user)
        await db.flush()
    elif phone and not user.phone_enc:
        user.phone_enc = encrypt(phone)
    return user


def _require_production_phone(phone: str | None) -> None:
    if not settings.DEBUG and not phone:
        raise ValueError("微信手机号授权失败，请重新授权后登录")


def _new_doctor_audit_status() -> str:
    # 即使生产误配 DOCTOR_AUTO_APPROVE=true，也不能自动放行新医生。
    return "approved" if settings.DEBUG and settings.DOCTOR_AUTO_APPROVE else "pending"


async def login_patient(db: AsyncSession, code: str, phone_code: str | None, dev_phone: str | None) -> tuple[User, str]:
    openid = await wx_code2session(code, settings.WX_PATIENT_APPID, settings.WX_PATIENT_SECRET)
    if not openid:
        raise ValueError("微信登录失败")
    phone = await _resolve_phone(phone_code, dev_phone, settings.WX_PATIENT_APPID, settings.WX_PATIENT_SECRET)
    _require_production_phone(phone)
    user = await _get_or_create_user(db, openid, Role.PATIENT, phone)
    token = create_token(sub=str(user.id), role=Role.PATIENT)
    return user, token


async def login_doctor(db: AsyncSession, code: str, phone_code: str | None, dev_phone: str | None) -> tuple[User, str]:
    openid = await wx_code2session(code, settings.WX_DOCTOR_APPID, settings.WX_DOCTOR_SECRET)
    if not openid:
        raise ValueError("微信登录失败")
    phone = await _resolve_phone(phone_code, dev_phone, settings.WX_DOCTOR_APPID, settings.WX_DOCTOR_SECRET)
    _require_production_phone(phone)
    user = await _get_or_create_user(db, openid, Role.DOCTOR, phone)

    # 允许登录；接诊/开方权限由 audit_status 把关（未审医生进资质提交页，见 require_approved_doctor）。
    # 首次登录建一条医生记录：开发期自动通过，生产期 pending 待 admin 终审。
    res = await db.execute(select(Doctor).where(Doctor.user_id == user.id))
    doctor = res.scalar_one_or_none()
    if doctor is None:
        doctor = Doctor(user_id=user.id, audit_status=_new_doctor_audit_status())
        db.add(doctor)
        await db.flush()

    token = create_token(sub=str(user.id), role=Role.DOCTOR)
    return user, token
