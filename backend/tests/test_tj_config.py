from types import SimpleNamespace

from app.services.tj_config import gateway_config_errors, is_production_gateway, is_test_gateway


def _config(**overrides):
    values = {
        "TJ_GATEWAY_URL": "https://imssp.wsjk.tj.gov.cn/net-diag-service/openapi/api",
        "TJ_APP_KEY": "0123456789abcdef",
        "TJ_APP_SECRET": "0123456789abcdef0123456789abcdef",
        "TJ_UNIT_ID": "20250813151647906",
        "ORGAN_ID": "91120116MACJA9PX45",
        "ORGAN_NAME": "天津逑贝互联网医院",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_gateway_environment_detection():
    test = "https://imssp.wsjk.tj.gov.cn/net-diag-service/test-openapi/api"
    prod = "https://imssp.wsjk.tj.gov.cn/net-diag-service/openapi/api"
    assert is_test_gateway(test)
    assert not is_production_gateway(test)
    assert is_production_gateway(prod)


def test_valid_production_config():
    assert gateway_config_errors(_config(), require_production=True) == []


def test_rejects_test_gateway_for_production_and_bad_secret():
    errors = gateway_config_errors(_config(
        TJ_GATEWAY_URL="https://imssp.wsjk.tj.gov.cn/net-diag-service/test-openapi/api",
        TJ_APP_SECRET="not-a-key",
    ), require_production=True)
    assert "当前不是正式网关地址" in errors
    assert "TJ_APP_SECRET 必须是 32 位十六进制字符串" in errors
