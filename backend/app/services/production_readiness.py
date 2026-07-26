"""生产环境只读配置预检。

只报告可公开的配置状态，不输出任何密钥值，也不修改配置、数据库或外部系统。
"""
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from ..core.config import settings


@dataclass(frozen=True)
class ReadinessCheck:
    level: str
    area: str
    message: str


def _get(config, name: str):
    return getattr(config, name, None)


def _missing(config, names: tuple[str, ...]) -> list[str]:
    return [name for name in names if not str(_get(config, name) or "").strip()]


def _valid_https_url(value: str, *, origin_only: bool = False) -> bool:
    try:
        parsed = urlparse(value or "")
    except ValueError:
        return False
    if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
        return False
    if origin_only and (parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        return False
    return True


def _resolve_path(value: str, backend_dir: Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else backend_dir / path


def configuration_checks(config=settings, *, backend_dir: Path | None = None) -> list[ReadinessCheck]:
    """检查生产基础配置，返回脱敏后的 PASS/WARN/FAIL 项。"""
    root = backend_dir or Path(__file__).resolve().parents[2]
    checks: list[ReadinessCheck] = []

    if bool(_get(config, "DEBUG")):
        checks.append(ReadinessCheck("FAIL", "运行模式", "DEBUG 必须为 false"))
    else:
        checks.append(ReadinessCheck("PASS", "运行模式", "DEBUG=false"))

    jwt_secret = str(_get(config, "JWT_SECRET") or "")
    if jwt_secret == "CHANGE_ME_IN_PROD" or len(jwt_secret.encode("utf-8")) < 32:
        checks.append(ReadinessCheck("FAIL", "JWT", "JWT_SECRET 必须替换为至少 32 字节的随机密钥"))
    else:
        checks.append(ReadinessCheck("PASS", "JWT", "JWT_SECRET 已替换（值未输出）"))

    encryption_key = str(_get(config, "ENCRYPTION_KEY") or "")
    try:
        if not encryption_key:
            raise ValueError
        Fernet(encryption_key.encode())
    except (TypeError, ValueError):
        checks.append(ReadinessCheck("FAIL", "数据加密", "ENCRYPTION_KEY 未配置或不是有效 Fernet 密钥"))
    else:
        checks.append(ReadinessCheck("PASS", "数据加密", "ENCRYPTION_KEY 格式有效（值未输出）"))

    database_url = str(_get(config, "DATABASE_URL") or "")
    if not database_url:
        checks.append(ReadinessCheck("FAIL", "数据库", "DATABASE_URL 未配置"))
    elif any(marker in database_url for marker in ("://root:root@", "://qiubei:qiubei@")):
        checks.append(ReadinessCheck("WARN", "数据库", "DATABASE_URL 仍使用仓库开发口令，应计划安全轮换"))
    else:
        checks.append(ReadinessCheck("PASS", "数据库", "DATABASE_URL 未使用仓库开发口令（值未输出）"))

    origins = [item.strip() for item in str(_get(config, "CORS_ORIGINS") or "").split(",") if item.strip()]
    invalid_origins = [origin for origin in origins if not _valid_https_url(origin, origin_only=True)]
    if not origins:
        checks.append(ReadinessCheck("FAIL", "CORS", "CORS_ORIGINS 未配置运营后台 HTTPS 来源"))
    elif invalid_origins:
        checks.append(ReadinessCheck("FAIL", "CORS", f"CORS_ORIGINS 中有 {len(invalid_origins)} 个非 HTTPS 标准来源"))
    else:
        checks.append(ReadinessCheck("PASS", "CORS", f"已配置 {len(origins)} 个 HTTPS 来源"))

    login_fields = ("WX_PATIENT_APPID", "WX_PATIENT_SECRET", "WX_DOCTOR_APPID", "WX_DOCTOR_SECRET")
    missing_login = _missing(config, login_fields)
    if missing_login:
        checks.append(ReadinessCheck("FAIL", "微信登录", f"缺少配置：{', '.join(missing_login)}"))
    else:
        checks.append(ReadinessCheck("PASS", "微信登录", "患者端与医生端凭据齐全（值未输出）"))

    pay_fields = (
        "WX_APPID", "WX_MCHID", "WX_API_V3_KEY", "WX_MCH_CERT_SERIAL",
        "WX_MCH_PRIVATE_KEY_PATH", "WX_PAY_NOTIFY_URL",
    )
    missing_pay = _missing(config, pay_fields)
    if missing_pay:
        checks.append(ReadinessCheck("FAIL", "微信支付", f"缺少配置：{', '.join(missing_pay)}"))
    else:
        api_key = str(_get(config, "WX_API_V3_KEY") or "")
        if len(api_key.encode("utf-8")) != 32:
            checks.append(ReadinessCheck("FAIL", "微信支付", "WX_API_V3_KEY 必须为 32 字节"))
        notify_url = str(_get(config, "WX_PAY_NOTIFY_URL") or "")
        if not _valid_https_url(notify_url):
            checks.append(ReadinessCheck("FAIL", "微信支付", "WX_PAY_NOTIFY_URL 必须为公网 HTTPS 地址"))
        if _get(config, "WX_APPID") != _get(config, "WX_PATIENT_APPID"):
            checks.append(ReadinessCheck("FAIL", "微信支付", "WX_APPID 必须与患者端 AppID 一致"))
        key_path = _resolve_path(str(_get(config, "WX_MCH_PRIVATE_KEY_PATH")), root)
        try:
            private_key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
            if not isinstance(private_key, RSAPrivateKey):
                raise ValueError
        except (OSError, TypeError, ValueError, UnsupportedAlgorithm):
            checks.append(ReadinessCheck("FAIL", "微信支付", "商户私钥文件不存在或不是有效 RSA 私钥"))
        if not any(item.level == "FAIL" and item.area == "微信支付" for item in checks):
            checks.append(ReadinessCheck("PASS", "微信支付", "下单、回调和商户私钥配置有效（值未输出）"))

    sms_fields = (
        "TENCENT_SMS_SECRET_ID", "TENCENT_SMS_SECRET_KEY", "TENCENT_SMS_SDK_APP_ID",
        "TENCENT_SMS_SIGN", "TENCENT_SMS_TEMPLATE_ID",
    )
    missing_sms = _missing(config, sms_fields)
    if len(missing_sms) == len(sms_fields):
        checks.append(ReadinessCheck("WARN", "短信", "腾讯云短信尚未配置，生产验证码接口会安全拒绝"))
    elif missing_sms:
        checks.append(ReadinessCheck("FAIL", "短信", f"腾讯云短信配置不完整，缺少：{', '.join(missing_sms)}"))
    else:
        checks.append(ReadinessCheck("PASS", "短信", "腾讯云短信字段齐全（尚需真机收码验证）"))

    if not _get(config, "TRTC_SDKAPPID") or not _get(config, "TRTC_SECRETKEY"):
        checks.append(ReadinessCheck("WARN", "音视频", "TRTC 配置不完整，视频问诊不可用"))
    else:
        checks.append(ReadinessCheck("PASS", "音视频", "TRTC 服务端字段齐全（尚需官方小程序 SDK）"))

    if bool(_get(config, "DOCTOR_AUTO_APPROVE")):
        checks.append(ReadinessCheck("WARN", "医生审核", "DOCTOR_AUTO_APPROVE=true；生产代码仍强制新医生待审，建议改为 false"))
    else:
        checks.append(ReadinessCheck("PASS", "医生审核", "DOCTOR_AUTO_APPROVE=false"))

    if not any(bool(_get(config, name)) for name in ("FXQ_CA_ENABLED", "FXQ_DOCUMENT_SIGN_ENABLED", "FXQ_CA_REQUIRED")):
        checks.append(ReadinessCheck("WARN", "放心签", "放心签生产门禁尚未开启"))
    else:
        from .fxq_ca import config_errors

        errors = config_errors(config)
        checks.extend(ReadinessCheck("FAIL", "放心签", error) for error in errors)
        if not errors:
            checks.append(ReadinessCheck("PASS", "放心签", "配置字段、有效期与官方域名检查通过"))

    if bool(_get(config, "TJ_REPORT_ENABLED")):
        from .tj_config import gateway_config_errors

        errors = gateway_config_errors(config, require_production=True)
        checks.extend(ReadinessCheck("FAIL", "天津监管", error) for error in errors)
        if not errors:
            checks.append(ReadinessCheck("PASS", "天津监管", "正式网关配置格式有效（凭据未输出）"))
    else:
        checks.append(ReadinessCheck("WARN", "天津监管", "TJ_REPORT_ENABLED=false，正式上报尚未开启"))

    env_path = root / ".env"
    if os.name == "posix" and env_path.exists():
        mode = stat.S_IMODE(env_path.stat().st_mode)
        if mode & 0o077:
            checks.append(ReadinessCheck("FAIL", "文件权限", ".env 可被属组或其他用户读取，应 chmod 600"))
        else:
            checks.append(ReadinessCheck("PASS", "文件权限", ".env 权限未向属组或其他用户开放"))

    return checks
