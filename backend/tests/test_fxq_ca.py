"""放心签高级证书协议/智能双录客户端测试（全程 MockTransport，不访问外网）。"""
import json
from types import SimpleNamespace

import httpx
import pytest

from app.services.fxq_ca import FxqCaClient, config_errors


def _config(**overrides):
    values = {
        "FXQ_CA_ENABLED": True,
        "FXQ_CA_REQUIRED": False,
        "FXQ_APP_KEY": "app-key",
        "FXQ_APP_SECRET": "app-secret",
        "FXQ_CA_REDIRECT_URL": "https://api.example.com/api/v1/ca/callback",
        "FXQ_TOKEN_URL": "https://restapi.fangxinqian.cn/auth/v1/token",
        "FXQ_REQUEST_SIGN_URL": "https://identity.fangxinqian.cn/auth/v1/encrypt",
        "FXQ_CA_AGREEMENT_URL": "https://identity.fangxinqian.cn/face/v1/agreement/dualrecording/ca",
        "FXQ_CA_RESULT_URL": "https://identity.fangxinqian.cn/face/v1/dualrecording/result",
        "FXQ_HTTP_TIMEOUT_SECONDS": 2.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.asyncio
async def test_start_agreement_uses_token_then_official_request_signature():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        calls.append((request.url.path, dict(request.headers), payload))
        if request.url.path == "/auth/v1/token":
            assert payload == {"key": "app-key", "secret": "app-secret"}
            return httpx.Response(200, json={"code": 10000, "data": "token-1", "msg": "成功"})
        if request.url.path == "/auth/v1/encrypt":
            assert request.headers["token"] == "token-1"
            assert payload["idNo"] == "120101199001011234"
            return httpx.Response(
                200, json={"code": 10000, "data": {"nonce": "nonce-1", "sign": "sign-1"}, "msg": "成功"}
            )
        assert request.url.path == "/face/v1/agreement/dualrecording/ca"
        assert request.headers["token"] == "token-1"
        assert request.headers["fxq-nonce"] == "nonce-1"
        assert request.headers["fxq-sign"] == "sign-1"
        return httpx.Response(
            200,
            json={
                "code": 10000,
                "data": {"verifyId": "verify-1", "agreementUrl": "https://identity.fangxinqian.cn/h5"},
                "msg": "成功",
                "tradeNo": "trade-1",
            },
        )

    client = FxqCaClient(config=_config(), transport=httpx.MockTransport(handler))
    result = await client.start_agreement(
        name="测试医生",
        id_no="120101199001011234",
        redirect_url="https://api.example.com/api/v1/ca/callback",
        user_id="qb_doctor_1",
        order_no="QBCA001",
    )

    assert [c[0] for c in calls] == [
        "/auth/v1/token",
        "/auth/v1/encrypt",
        "/face/v1/agreement/dualrecording/ca",
    ]
    assert result.data["verifyId"] == "verify-1"
    assert result.trade_no == "trade-1"


@pytest.mark.asyncio
async def test_result_query_explicitly_disables_photo_and_video_download():
    business_payload = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal business_payload
        payload = json.loads(request.content)
        if request.url.path == "/auth/v1/token":
            return httpx.Response(200, json={"code": 10000, "data": "token-1"})
        if request.url.path == "/auth/v1/encrypt":
            return httpx.Response(200, json={"code": 10000, "data": {"nonce": "n", "sign": "s"}})
        business_payload = payload
        return httpx.Response(
            200,
            json={
                "code": 10000,
                "data": {"faceCode": "0", "faceMsg": "请求成功", "orderNo": "QBCA001"},
                "msg": "成功",
            },
        )

    client = FxqCaClient(config=_config(), transport=httpx.MockTransport(handler))
    result = await client.query_result(order_no="QBCA001")

    assert result.data["faceCode"] == "0"
    assert business_payload == {
        "orderNo": "QBCA001",
        "getFile": "0",
        "getDetails": "1",
        "getPhotos": "0",
    }


@pytest.mark.asyncio
async def test_expired_token_is_refreshed_once():
    token_calls = 0
    business_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal token_calls, business_calls
        if request.url.path == "/auth/v1/token":
            token_calls += 1
            return httpx.Response(200, json={"code": 10000, "data": f"token-{token_calls}"})
        if request.url.path == "/auth/v1/encrypt":
            return httpx.Response(200, json={"code": 10000, "data": {"nonce": "n", "sign": "s"}})
        business_calls += 1
        if business_calls == 1:
            return httpx.Response(200, json={"code": 10005, "msg": "token已失效"})
        return httpx.Response(
            200, json={"code": 10000, "data": {"faceCode": "0", "orderNo": "QBCA001"}, "msg": "成功"}
        )

    client = FxqCaClient(config=_config(), transport=httpx.MockTransport(handler))
    result = await client.query_result(order_no="QBCA001")

    assert result.data["faceCode"] == "0"
    assert token_calls == 2
    assert business_calls == 2


def test_config_rejects_secret_exfiltration_to_non_official_host():
    errors = config_errors(_config(FXQ_CA_RESULT_URL="https://attacker.example/result"))
    assert any("FXQ_CA_RESULT_URL" in error for error in errors)


def test_required_mode_cannot_silently_disable_provider():
    errors = config_errors(_config(FXQ_CA_ENABLED=False, FXQ_CA_REQUIRED=True))
    assert any("FXQ_CA_ENABLED" in error for error in errors)
