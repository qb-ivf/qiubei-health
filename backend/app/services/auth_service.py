"""鉴权服务（M1）：微信登录 → 用户 → JWT；医生白名单。"""
import hashlib
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import Role
from ..core.config import settings
from ..core.crypto import encrypt
from ..core.security import create_token
from ..models.user import Doctor, User

logger = logging.getLogger("auth")


async def wx_code2session(code: str, appid: str, secret: str) -> str | None:
    """用 code 换 openid。无密钥（开发）时返回伪 openid。"""
    if not appid or not secret:
        # 开发回退：用 code 派生稳定 openid（仅本地联调）
        return "dev_" + hashlib.sha256(code.encode()).hexdigest()[:24]
    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {"appid": appid, "secret": secret, "js_code": code, "grant_type": "authorization_code"}
    async with httpx.AsyncClient(timeout=8) as client:
        r = await client.get(url, params=params)
        data = r.json()
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


async def login_patient(db: AsyncSession, code: str, dev_phone: str | None) -> tuple[User, str]:
    openid = await wx_code2session(code, settings.WX_PATIENT_APPID, settings.WX_PATIENT_SECRET)
    if not openid:
        raise ValueError("微信登录失败")
    user = await _get_or_create_user(db, openid, Role.PATIENT, dev_phone)
    token = create_token(sub=str(user.id), role=Role.PATIENT)
    return user, token


async def login_doctor(db: AsyncSession, code: str, dev_phone: str | None) -> tuple[User, str]:
    openid = await wx_code2session(code, settings.WX_DOCTOR_APPID, settings.WX_DOCTOR_SECRET)
    if not openid:
        raise ValueError("微信登录失败")
    user = await _get_or_create_user(db, openid, Role.DOCTOR, dev_phone)

    # 白名单校验（PRD §2.4）：必须是已认证医生
    res = await db.execute(select(Doctor).where(Doctor.user_id == user.id))
    doctor = res.scalar_one_or_none()
    if doctor is None:
        if not settings.DOCTOR_AUTO_APPROVE:
            raise PermissionError("非认证执业医师，无法登录")
        doctor = Doctor(user_id=user.id, audit_status="approved")  # 开发期自动通过
        db.add(doctor)
        await db.flush()
    elif doctor.audit_status != "approved":
        raise PermissionError("医生资质审核未通过")

    token = create_token(sub=str(user.id), role=Role.DOCTOR)
    return user, token
