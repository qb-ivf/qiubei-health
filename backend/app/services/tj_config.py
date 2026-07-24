"""天津监管网关配置校验（不读取/输出密钥明文）。"""
import re
from urllib.parse import urlparse


def is_test_gateway(url: str) -> bool:
    return "/net-diag-service/test-openapi/api" in (url or "")


def is_production_gateway(url: str) -> bool:
    return "/net-diag-service/openapi/api" in (url or "") and not is_test_gateway(url)


def gateway_config_errors(config, *, require_production: bool = False) -> list[str]:
    """返回可公开展示的配置错误；错误文本不会包含凭据值。"""
    errors: list[str] = []
    url = (getattr(config, "TJ_GATEWAY_URL", "") or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        errors.append("TJ_GATEWAY_URL 不是有效的 HTTP(S) 地址")
    elif not (is_test_gateway(url) or is_production_gateway(url)):
        errors.append("TJ_GATEWAY_URL 路径不是平台 test-openapi/openapi 地址")
    if require_production and not is_production_gateway(url):
        errors.append("当前不是正式网关地址")
    if require_production and parsed.scheme != "https":
        errors.append("正式网关必须使用 HTTPS 互联网地址")

    if not (getattr(config, "TJ_APP_KEY", "") or "").strip():
        errors.append("TJ_APP_KEY 未配置")
    secret = (getattr(config, "TJ_APP_SECRET", "") or "").strip()
    if not re.fullmatch(r"[0-9a-fA-F]{32}", secret):
        errors.append("TJ_APP_SECRET 必须是 32 位十六进制字符串")
    if not (getattr(config, "TJ_UNIT_ID", "") or "").strip():
        errors.append("TJ_UNIT_ID 未配置")
    organ_id = (getattr(config, "ORGAN_ID", "") or "").strip().upper()
    if not re.fullmatch(r"[0-9A-Z]{18}", organ_id):
        errors.append("ORGAN_ID 必须是 18 位统一社会信用代码")
    if not (getattr(config, "ORGAN_NAME", "") or "").strip():
        errors.append("ORGAN_NAME 未配置")
    return errors
