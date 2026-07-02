"""天津监管平台网关客户端（S1，docs/tianjin_supervision_plan.md）。

职责：把已组装好的业务 payload（数组）加密、签名并发送到监管平台，解析返回。
字段映射不在这里做（见 S3 tj_mappers）；重试调度也不在这里做（compliance worker 负责，
本模块只负责"单次调用 + 结果分类"）。

用法：
    result = await tj_call("uploadDrugCatalogue", [ {...}, {...} ])
    if result.ok: ...
    elif result.retryable: 交给退避重试
    else: 数据问题，进失败列表待人工
"""
import json
import logging
from dataclasses import dataclass

import httpx

from ..core.config import settings
from ..utils.sm_crypto import build_sign_headers, sm3_hex_upper, sm4_cbc_encrypt_hex

logger = logging.getLogger(__name__)

# 可自动重试的错误：系统繁忙 / 请求过期（时钟漂移）/ 网络层
_RETRYABLE_CODES = {-1, 40011}


@dataclass
class TjResult:
    ok: bool
    retryable: bool
    code: int          # HTTP 层 code（网络异常时为 -1000）
    msg_code: int | None
    msg: str
    raw: str = ""
    data: list | None = None   # 平台返回 data（如 uploadFile 的附件 id 集合）


def _classify(code: int, msg_code: int | None, msg: str, raw: str) -> TjResult:
    if code == 200 and msg_code == 200:
        return TjResult(True, False, code, msg_code, msg, raw)
    retryable = code in _RETRYABLE_CODES
    return TjResult(False, retryable, code, msg_code, msg, raw)


async def tj_call(method: str, payload: list) -> TjResult:
    """调用监管平台业务接口（请求体 SM4 加密）。payload 最外层必须是数组。"""
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    encrypted = sm4_cbc_encrypt_hex(body, settings.TJ_APP_SECRET)
    headers = build_sign_headers(method, sm3_hex_upper(encrypted), settings.TJ_APP_KEY)
    return await _post(settings.TJ_GATEWAY_URL, encrypted, headers, method)


async def tj_upload_file(file_name: str, content_base64: str, size: str, file_type: str) -> TjResult:
    """附件上传（api/uploadFile）：走明文路径（SDK executeNoEncode），不做 SM4 加密。

    成功时监管平台附件 id 集合在响应 data 字段，调用方从 raw 解析。
    路径拼接以联调实测为准（规范 2.1.3.3：接口地址为 api/uploadFile）。
    """
    body = json.dumps(
        [{"fileName": file_name, "contentBase64": content_base64, "size": size, "type": file_type}],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    headers = build_sign_headers("upload", sm3_hex_upper(body), settings.TJ_APP_KEY)
    url = settings.TJ_GATEWAY_URL.rstrip("/") + "/uploadFile"
    return await _post(url, body, headers, "uploadFile")


async def _post(url: str, content: str, headers: dict, method: str) -> TjResult:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, content=content, headers=headers)
    except httpx.HTTPError as e:
        logger.warning("监管平台网络异常 method=%s: %s", method, e)
        return TjResult(False, True, -1000, None, f"网络异常: {e}")

    raw = resp.text
    if resp.status_code != 200:
        # 网关层非 200：按可重试处理（5xx/网关抖动）
        logger.warning("监管平台 HTTP %s method=%s: %s", resp.status_code, method, raw[:200])
        return TjResult(False, True, -1000, None, f"HTTP {resp.status_code}", raw)

    try:
        data = resp.json()
        code = int(data.get("code", -1))
        body = data.get("body") or {}
        # body 可能是对象或数组（部分接口返回 [ {msgCode, msg} ]）
        if isinstance(body, list):
            body = body[0] if body else {}
        msg_code = int(body.get("msgCode")) if body.get("msgCode") is not None else None
        msg = str(body.get("msg", ""))
        resp_data = data.get("data") if isinstance(data.get("data"), list) else None
    except (ValueError, TypeError, json.JSONDecodeError):
        logger.warning("监管平台响应解析失败 method=%s: %s", method, raw[:200])
        return TjResult(False, True, -1000, None, "响应解析失败", raw)

    result = _classify(code, msg_code, msg, raw)
    result.data = resp_data
    if not result.ok:
        logger.warning(
            "监管平台上报失败 method=%s code=%s msgCode=%s msg=%s retryable=%s",
            method, code, msg_code, msg, result.retryable,
        )
    return result
