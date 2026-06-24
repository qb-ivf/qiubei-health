"""JWT 鉴权 + 密码哈希 + 隐私脱敏（PRD §2.4）。"""
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from .config import settings


# —— 运营后台账号密码哈希（直接用 bcrypt，避开 passlib 与 bcrypt4.x 的兼容问题）——
def hash_password(password: str) -> str:
    pw = password.encode("utf-8")[:72]  # bcrypt 上限 72 字节
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], password_hash.encode("utf-8"))
    except Exception:  # noqa: BLE001 哈希格式异常等
        return False


def create_token(sub: str, role: str, **extra) -> str:
    payload = {
        "sub": sub,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES),
        **extra,
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
    except JWTError:
        return None


# —— 隐私去隐私化（列表/病历默认脱敏，仅诊室内医生可解密完整档案） ——
def mask_name(name: str) -> str:
    if not name:
        return name
    return name[0] + "*" * (len(name) - 1) if len(name) <= 2 else name[0] + "*" + name[-1]


def mask_phone(phone: str) -> str:
    return phone[:3] + "****" + phone[-4:] if phone and len(phone) == 11 else phone


def mask_id_card(idc: str) -> str:
    return idc[:3] + "*" * (len(idc) - 7) + idc[-4:] if idc and len(idc) >= 8 else idc
