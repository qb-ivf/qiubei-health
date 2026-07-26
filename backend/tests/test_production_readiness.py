from types import SimpleNamespace

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.services.production_readiness import configuration_checks


def _private_key_file(tmp_path):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    path = tmp_path / "merchant.pem"
    path.write_bytes(key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ))
    return path


def _config(tmp_path, **overrides):
    values = {
        "DEBUG": False,
        "JWT_SECRET": "a" * 64,
        "ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "DATABASE_URL": "mysql+aiomysql://app:random-password@mysql:3306/qiubei",
        "CORS_ORIGINS": "https://admin.qb-medical.cn",
        "WX_PATIENT_APPID": "patient-appid",
        "WX_PATIENT_SECRET": "patient-secret",
        "WX_DOCTOR_APPID": "doctor-appid",
        "WX_DOCTOR_SECRET": "doctor-secret",
        "WX_APPID": "patient-appid",
        "WX_MCHID": "merchant-id",
        "WX_API_V3_KEY": "v" * 32,
        "WX_MCH_CERT_SERIAL": "serial",
        "WX_MCH_PRIVATE_KEY_PATH": str(_private_key_file(tmp_path)),
        "WX_PAY_NOTIFY_URL": "https://api.qb-medical.cn/api/v1/orders/pay/callback",
        "TENCENT_SMS_SECRET_ID": "sms-id",
        "TENCENT_SMS_SECRET_KEY": "sms-key",
        "TENCENT_SMS_SDK_APP_ID": "sms-app",
        "TENCENT_SMS_SIGN": "短信签名",
        "TENCENT_SMS_TEMPLATE_ID": "template",
        "TRTC_SDKAPPID": 123,
        "TRTC_SECRETKEY": "trtc-secret",
        "DOCTOR_AUTO_APPROVE": False,
        "FXQ_CA_ENABLED": False,
        "FXQ_DOCUMENT_SIGN_ENABLED": False,
        "FXQ_CA_REQUIRED": False,
        "TJ_REPORT_ENABLED": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _messages(checks):
    return "\n".join(item.message for item in checks)


def test_ready_core_configuration_has_no_failures(tmp_path):
    checks = configuration_checks(_config(tmp_path), backend_dir=tmp_path)

    assert not [item for item in checks if item.level == "FAIL"]
    assert any(item.area == "微信支付" and item.level == "PASS" for item in checks)


def test_preflight_rejects_default_secrets_debug_and_missing_cors(tmp_path):
    config = _config(
        tmp_path,
        DEBUG=True,
        JWT_SECRET="CHANGE_ME_IN_PROD",
        ENCRYPTION_KEY="",
        CORS_ORIGINS="",
    )

    checks = configuration_checks(config, backend_dir=tmp_path)
    failed_areas = {item.area for item in checks if item.level == "FAIL"}

    assert {"运行模式", "JWT", "数据加密", "CORS"} <= failed_areas


def test_preflight_rejects_invalid_payment_and_partial_sms(tmp_path):
    config = _config(
        tmp_path,
        WX_APPID="wrong-appid",
        WX_API_V3_KEY="too-short",
        WX_PAY_NOTIFY_URL="https://[",
        TENCENT_SMS_TEMPLATE_ID="",
    )

    checks = configuration_checks(config, backend_dir=tmp_path)
    failed_areas = {item.area for item in checks if item.level == "FAIL"}

    assert {"微信支付", "短信"} <= failed_areas


def test_preflight_messages_never_echo_secret_values(tmp_path):
    config = _config(
        tmp_path,
        JWT_SECRET="jwt-secret-that-must-never-be-printed",
        WX_PATIENT_SECRET="wechat-secret-that-must-never-be-printed",
        TENCENT_SMS_SECRET_KEY="sms-secret-that-must-never-be-printed",
    )

    messages = _messages(configuration_checks(config, backend_dir=tmp_path))

    assert config.JWT_SECRET not in messages
    assert config.WX_PATIENT_SECRET not in messages
    assert config.TENCENT_SMS_SECRET_KEY not in messages
