"""敏感字段对称加密（身份证/手机号落库前加密，PRD §2.4）。"""
import base64
import hashlib
import logging

from cryptography.fernet import Fernet

from .config import settings

logger = logging.getLogger("crypto")


def _key() -> bytes:
    if settings.ENCRYPTION_KEY:
        return settings.ENCRYPTION_KEY.encode()
    logger.warning("ENCRYPTION_KEY 未设置，使用开发回退密钥（勿用于生产）")
    digest = hashlib.sha256(settings.JWT_SECRET.encode()).digest()
    return base64.urlsafe_b64encode(digest)


_fernet = Fernet(_key())


def encrypt(text: str | None) -> str | None:
    return _fernet.encrypt(text.encode()).decode() if text else text


def decrypt(token: str | None) -> str | None:
    return _fernet.decrypt(token.encode()).decode() if token else token
