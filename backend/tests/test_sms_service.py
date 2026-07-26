from __future__ import annotations

import pytest

from app.core.config import settings
from app.services import sms_service


class FakeRedis:
    def __init__(self):
        self.values: dict[str, str | int] = {}
        self.expirations: dict[str, int] = {}

    async def set(self, key, value, *, ex=None, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        if ex is not None:
            self.expirations[key] = ex
        return True

    async def get(self, key):
        return self.values.get(key)

    async def incr(self, key):
        value = int(self.values.get(key, 0)) + 1
        self.values[key] = value
        return value

    async def expire(self, key, seconds):
        self.expirations[key] = seconds
        return True

    async def delete(self, key):
        return int(self.values.pop(key, None) is not None)


def _configure_sms(monkeypatch):
    values = {
        "DEBUG": False,
        "JWT_SECRET": "j" * 64,
        "TENCENT_SMS_SECRET_ID": "secret-id",
        "TENCENT_SMS_SECRET_KEY": "secret-key",
        "TENCENT_SMS_SDK_APP_ID": "1400000000",
        "TENCENT_SMS_SIGN": "天津逑贝互联网医院",
        "TENCENT_SMS_TEMPLATE_REGISTER_PHONE_ID": "2695131",
        "TENCENT_SMS_TEMPLATE_CHANGE_PHONE_ID": "2695133",
        "TENCENT_SMS_CODE_TTL_SECONDS": 300,
        "TENCENT_SMS_SEND_INTERVAL_SECONDS": 60,
        "TENCENT_SMS_PHONE_DAILY_LIMIT": 2,
        "TENCENT_SMS_USER_HOURLY_LIMIT": 5,
        "TENCENT_SMS_IP_HOURLY_LIMIT": 30,
    }
    for key, value in values.items():
        monkeypatch.setattr(settings, key, value)


def test_templates_match_approved_parameter_order(monkeypatch):
    _configure_sms(monkeypatch)

    assert sms_service._template_id("register_phone") == "2695131"
    assert sms_service._template_params("register_phone", "123456") == ["123456", "5"]
    assert sms_service._template_id("change_phone") == "2695133"
    assert sms_service._template_params("change_phone", "123456") == ["123456"]


@pytest.mark.asyncio
async def test_success_stores_code_only_after_provider_accepts(monkeypatch):
    _configure_sms(monkeypatch)
    fake_redis = FakeRedis()
    captured = {}

    async def fake_send(phone, code, purpose):
        captured.update(phone=phone, code=code, purpose=purpose)
        return sms_service.TencentSmsResult(True, "Ok", "request-id")

    monkeypatch.setattr(sms_service, "redis_client", fake_redis)
    monkeypatch.setattr(sms_service, "_send_tencent", fake_send)

    ok, message, dev_code = await sms_service.send_code(
        "13800000000",
        "register_phone",
        user_id=7,
    )

    assert (ok, message, dev_code) == (True, "验证码已发送", None)
    assert captured["purpose"] == "register_phone"
    code_keys = [key for key in fake_redis.values if key.startswith("sms:code:")]
    assert len(code_keys) == 1
    assert fake_redis.values[code_keys[0]] == captured["code"]
    assert "13800000000" not in "\n".join(fake_redis.values.keys())


@pytest.mark.asyncio
async def test_provider_failure_never_stores_verifiable_code(monkeypatch):
    _configure_sms(monkeypatch)
    fake_redis = FakeRedis()

    async def fake_send(_phone, _code, _purpose):
        return sms_service.TencentSmsResult(False, "FailedOperation", "request-id")

    monkeypatch.setattr(sms_service, "redis_client", fake_redis)
    monkeypatch.setattr(sms_service, "_send_tencent", fake_send)

    ok, _, dev_code = await sms_service.send_code(
        "13800000000",
        "change_phone",
        user_id=7,
    )

    assert ok is False
    assert dev_code is None
    assert not [key for key in fake_redis.values if key.startswith("sms:code:")]


@pytest.mark.asyncio
async def test_phone_interval_and_account_hourly_limits(monkeypatch):
    _configure_sms(monkeypatch)
    fake_redis = FakeRedis()

    async def fake_send(_phone, _code, _purpose):
        return sms_service.TencentSmsResult(True, "Ok", "request-id")

    monkeypatch.setattr(sms_service, "redis_client", fake_redis)
    monkeypatch.setattr(sms_service, "_send_tencent", fake_send)

    first = await sms_service.send_code(
        "13800000000",
        "register_phone",
        user_id=7,
    )
    second = await sms_service.send_code(
        "13800000000",
        "register_phone",
        user_id=7,
    )

    assert first[0] is True
    assert second[0] is False
    assert "频繁" in second[1]


@pytest.mark.asyncio
async def test_same_ip_is_limited_across_different_phone_numbers(monkeypatch):
    _configure_sms(monkeypatch)
    monkeypatch.setattr(settings, "TENCENT_SMS_IP_HOURLY_LIMIT", 1)
    fake_redis = FakeRedis()

    async def fake_send(_phone, _code, _purpose):
        return sms_service.TencentSmsResult(True, "Ok", "request-id")

    monkeypatch.setattr(sms_service, "redis_client", fake_redis)
    monkeypatch.setattr(sms_service, "_send_tencent", fake_send)

    first = await sms_service.send_code(
        "13800000000",
        "register_phone",
        user_id=7,
        client_ip="203.0.113.10",
    )
    second = await sms_service.send_code(
        "13900000000",
        "register_phone",
        user_id=7,
        client_ip="203.0.113.10",
    )

    assert first[0] is True
    assert second[0] is False
    assert "网络" in second[1]
    assert "203.0.113.10" not in "\n".join(fake_redis.values.keys())


@pytest.mark.asyncio
async def test_verification_code_is_one_time(monkeypatch):
    _configure_sms(monkeypatch)
    fake_redis = FakeRedis()
    monkeypatch.setattr(sms_service, "redis_client", fake_redis)
    key = sms_service._CODE_KEY.format(
        phone_token=sms_service._phone_token("13800000000")
    )
    fake_redis.values[key] = "123456"

    assert await sms_service.verify_code("13800000000", "000000") is False
    assert await sms_service.verify_code("13800000000", "123456") is True
    assert await sms_service.verify_code("13800000000", "123456") is False
