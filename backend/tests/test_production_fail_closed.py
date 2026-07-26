"""生产环境配置缺失时必须拒绝，不能回退伪登录、伪短信或模拟支付。"""
from types import SimpleNamespace

import httpx
import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.v1 import orders
from app.core.config import settings
from app.services import auth_service, pay_service, sms_service


@pytest.mark.asyncio
async def test_production_missing_wechat_credentials_cannot_make_dev_openid(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", False)

    openid = await auth_service.wx_code2session("temporary-code", "", "")

    assert openid is None


@pytest.mark.asyncio
async def test_wechat_network_failure_is_handled(monkeypatch):
    class _FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            raise httpx.ConnectError("network unavailable")

    monkeypatch.setattr(auth_service.httpx, "AsyncClient", lambda **_kwargs: _FailingClient())

    openid = await auth_service.wx_code2session(
        "temporary-code",
        "configured-appid",
        "configured-secret",
    )

    assert openid is None


@pytest.mark.asyncio
async def test_debug_missing_wechat_credentials_can_make_dev_openid(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", True)

    openid = await auth_service.wx_code2session("temporary-code", "", "")

    assert openid.startswith("dev_")


@pytest.mark.asyncio
async def test_production_ignores_dev_phone(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", False)

    phone = await auth_service._resolve_phone(
        phone_code=None,
        dev_phone="13800000000",
        appid="",
        secret="",
    )

    assert phone is None


def test_production_requires_real_phone(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", False)

    with pytest.raises(ValueError, match="手机号授权失败"):
        auth_service._require_production_phone(None)


def test_production_never_auto_approves_new_doctor(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", False)
    monkeypatch.setattr(settings, "DOCTOR_AUTO_APPROVE", True)

    assert auth_service._new_doctor_audit_status() == "pending"


@pytest.mark.asyncio
async def test_production_missing_payment_config_rejects_mock_prepay(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", False)
    monkeypatch.setattr(pay_service, "is_enabled", lambda: False)

    with pytest.raises(pay_service.PayError, match="拒绝创建模拟支付"):
        await pay_service.prepay("QB1", 1, "openid", "挂号费", 1)


@pytest.mark.asyncio
async def test_debug_missing_payment_config_still_allows_explicit_mock(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", True)
    monkeypatch.setattr(pay_service, "is_enabled", lambda: False)

    result = await pay_service.prepay("QB1", 1, "openid", "挂号费", 1)

    assert "mock_" in result.package


def test_production_mock_payment_endpoint_is_hidden(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", False)

    with pytest.raises(HTTPException) as exc:
        orders._require_debug_mock()

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_debug_mock_payment_checks_order_owner(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", True)

    class _Db:
        async def get(self, _model, _key):
            return SimpleNamespace(user_id=99)

    with pytest.raises(HTTPException) as exc:
        await orders.pay_mock(order_id=8, uid=7, db=_Db())

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_production_unverified_payment_callback_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", False)
    monkeypatch.setattr(pay_service, "is_enabled", lambda: False)
    body = b'{"order_no":"QB-FORGED"}'
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(
        {"type": "http", "method": "POST", "path": "/", "headers": []},
        receive,
    )
    response = await orders.pay_callback(request, db=None)

    assert response.status_code == 503
    assert b"FAIL" in response.body


@pytest.mark.asyncio
async def test_production_unconfigured_sms_never_returns_dev_code(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", False)
    monkeypatch.setattr(sms_service, "_tencent_configured", lambda _purpose: False)

    ok, message, dev_code = await sms_service.send_code(
        "13800000000",
        sms_service.SMS_PURPOSE_REGISTER_PHONE,
        user_id=1,
    )

    assert ok is False
    assert "暂不可用" in message
    assert dev_code is None
