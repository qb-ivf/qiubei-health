"""放心签高级证书协议/智能双录客户端测试（全程 MockTransport，不访问外网）。"""
import json
from datetime import date
from types import SimpleNamespace

import httpx
import pytest

from app.services.fxq_ca import (
    FxqCaClient,
    FxqCaError,
    config_errors,
    expiry_status,
    signing_expiry_errors,
)


def _config(**overrides):
    values = {
        "FXQ_CA_ENABLED": True,
        "FXQ_DOCUMENT_SIGN_ENABLED": False,
        "FXQ_CA_REQUIRED": False,
        "FXQ_APP_KEY": "app-key",
        "FXQ_APP_SECRET": "app-secret",
        "FXQ_CA_REDIRECT_URL": "https://api.example.com/api/v1/ca/callback",
        "FXQ_TOKEN_URL": "https://identity.fangxinqian.cn/auth/v1/token",
        "FXQ_REQUEST_SIGN_URL": "https://identity.fangxinqian.cn/auth/v1/encrypt",
        "FXQ_CA_AGREEMENT_URL": "https://identity.fangxinqian.cn/face/v1/agreement/dualrecording/ca",
        "FXQ_CA_RESULT_URL": "https://identity.fangxinqian.cn/face/v1/dualrecording/result",
        "FXQ_COMPANY_NAME": "",
        "FXQ_COMPANY_IDNO": "",
        "FXQ_PERSONAL_SEAL_URL": "https://restapi.fangxinqian.cn/seal/v1/personal",
        "FXQ_COMPANY_SEAL_URL": "https://restapi.fangxinqian.cn/seal/v1/company",
        "FXQ_PDF_SIGN_URL": "https://restapi.fangxinqian.cn/contract/v1/port/sign",
        "FXQ_PDF_VERIFY_URL": "https://restapi.fangxinqian.cn/signature/chk/file",
        "FXQ_HTTP_TIMEOUT_SECONDS": 2.0,
        "FXQ_MAX_PDF_BYTES": 1024 * 1024,
        "FXQ_SERVICE_EXPIRES_ON": "",
        "FXQ_PERSONAL_CERT_EXPIRES_ON": "",
        "FXQ_EXPIRY_WARNING_DAYS": 30,
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
    assert any("FXQ_DOCUMENT_SIGN_ENABLED" in error for error in errors)


@pytest.mark.asyncio
async def test_document_endpoints_accept_string_data_and_download_only_pdf():
    signed_url = "https://fxq-contract-api.oss-cn-qingdao.aliyuncs.com/finish/rx.pdf"

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            assert str(request.url) == signed_url
            return httpx.Response(200, content=b"%PDF-1.7\nsigned")
        if request.url.path == "/auth/v1/token":
            return httpx.Response(200, json={"code": 10000, "data": "token-1"})
        if request.url.path == "/auth/v1/encrypt":
            return httpx.Response(200, json={"code": 10000, "data": {"nonce": "n", "sign": "s"}})
        if request.url.path == "/seal/v1/personal":
            return httpx.Response(200, json={"code": 10000, "data": signed_url, "tradeNo": "seal-1"})
        if request.url.path == "/contract/v1/port/sign":
            return httpx.Response(200, json={"code": 10000, "data": signed_url, "tradeNo": "sign-1"})
        if request.url.path == "/signature/chk/file":
            return httpx.Response(
                200,
                json={"code": 10000, "data": {"pdfModify": True, "signatureList": []}},
            )
        raise AssertionError(request.url.path)

    client = FxqCaClient(
        config=_config(
            FXQ_DOCUMENT_SIGN_ENABLED=True,
            FXQ_COMPANY_NAME="测试医院有限公司",
            FXQ_COMPANY_IDNO="91120116MACJA9PX45",
            FXQ_SERVICE_EXPIRES_ON="2099-01-01",
            FXQ_PERSONAL_CERT_EXPIRES_ON="2099-01-01",
        ),
        transport=httpx.MockTransport(handler),
    )
    seal = await client.generate_personal_seal(name="测试医生")
    signed = await client.sign_pdf(
        contract_base64="JVBERi0xLjc=",
        signers=[{"name": "测试医生", "idno": "120101199001011234", "seal": seal.data, "areas": []}],
    )
    verified = await client.verify_pdf(file_url=signed.data)
    downloaded = await client.download_pdf(file_url=signed.data)

    assert signed.trade_no == "sign-1"
    assert verified.data["pdfModify"] is True
    assert downloaded.startswith(b"%PDF-")


def test_document_signing_config_rejects_non_official_business_url():
    errors = config_errors(
        _config(
            FXQ_DOCUMENT_SIGN_ENABLED=True,
            FXQ_COMPANY_NAME="测试医院有限公司",
            FXQ_COMPANY_IDNO="91120116MACJA9PX45",
            FXQ_PDF_SIGN_URL="https://attacker.example/sign",
        )
    )
    assert any("FXQ_PDF_SIGN_URL" in error for error in errors)


def test_expiry_status_uses_earlier_date_and_warns_30_days_ahead():
    status = expiry_status(
        _config(
            FXQ_SERVICE_EXPIRES_ON="2027-07-23",
            FXQ_PERSONAL_CERT_EXPIRES_ON="2031-03-07",
        ),
        today=date(2027, 6, 23),
    )

    assert status.effective_expires_on == date(2027, 7, 23)
    assert status.days_until_expiry == 30
    assert "放心签服务套餐" in status.warning
    assert status.errors == ()


def test_expired_date_blocks_new_signing_but_not_enrollment_config():
    config = _config(FXQ_SERVICE_EXPIRES_ON="2026-01-01")
    status = expiry_status(config, today=date(2026, 1, 1))
    enrollment_errors = config_errors(config)
    signing_errors = signing_expiry_errors(config, today=date(2026, 1, 1))

    assert status.expired is True
    assert not any("已于" in error for error in enrollment_errors)
    assert any("已于" in error for error in signing_errors)


def test_invalid_expiry_config_is_not_ready():
    invalid = config_errors(
        _config(FXQ_PERSONAL_CERT_EXPIRES_ON="2031/03/07")
    )

    assert any("YYYY-MM-DD" in error for error in invalid)


def test_document_signing_requires_both_expiry_dates():
    errors = config_errors(
        _config(
            FXQ_DOCUMENT_SIGN_ENABLED=True,
            FXQ_COMPANY_NAME="测试医院有限公司",
            FXQ_COMPANY_IDNO="91120116MACJA9PX45",
        )
    )

    assert any("FXQ_SERVICE_EXPIRES_ON" in error for error in errors)
    assert any("FXQ_PERSONAL_CERT_EXPIRES_ON" in error for error in errors)


@pytest.mark.asyncio
async def test_signing_switch_is_enforced_inside_client():
    client = FxqCaClient(config=_config())

    with pytest.raises(FxqCaError, match="FXQ_DOCUMENT_SIGN_ENABLED"):
        await client.generate_personal_seal(name="测试医生")


@pytest.mark.asyncio
async def test_network_timeout_is_retryable_and_does_not_expose_credentials():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated provider timeout", request=request)

    client = FxqCaClient(config=_config(), transport=httpx.MockTransport(handler))

    with pytest.raises(FxqCaError) as captured:
        await client.check_auth()

    assert str(captured.value) == "放心签网络暂时不可用"
    assert captured.value.retryable is True
    assert "app-key" not in str(captured.value)
    assert "app-secret" not in str(captured.value)


@pytest.mark.asyncio
async def test_non_retryable_quota_error_is_not_called_twice():
    """供应商未确认正式余额错误码前，用普通非重试业务码模拟签章额度不足。"""
    business_calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal business_calls
        if request.url.path == "/auth/v1/token":
            return httpx.Response(200, json={"code": 10000, "data": "token-1"})
        if request.url.path == "/auth/v1/encrypt":
            return httpx.Response(
                200, json={"code": 10000, "data": {"nonce": "n", "sign": "s"}}
            )
        business_calls += 1
        return httpx.Response(200, json={"code": 24001, "msg": "签章额度不足"})

    client = FxqCaClient(
        config=_config(
            FXQ_DOCUMENT_SIGN_ENABLED=True,
            FXQ_COMPANY_NAME="测试医院有限公司",
            FXQ_COMPANY_IDNO="91120116MACJA9PX45",
            FXQ_SERVICE_EXPIRES_ON="2099-01-01",
            FXQ_PERSONAL_CERT_EXPIRES_ON="2099-01-01",
        ),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(FxqCaError, match="签章额度不足") as captured:
        await client.generate_personal_seal(name="测试医生")

    assert captured.value.code == 24001
    assert captured.value.retryable is False
    assert business_calls == 1
