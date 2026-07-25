"""放心签高级证书协议、智能双录与文档签署 HTTP 客户端。

调用链与开放平台保持一致：
  1) AppKey/AppSecret -> token
  2) token + 原始请求体 -> 官方 encrypt 接口生成 fxq-nonce/fxq-sign
  3) token/fxq-nonce/fxq-sign + 同一请求体 -> 业务接口

严禁记录 token、AppSecret、身份证号、agreementUrl、签章图片或响应中的照片/视频。
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import httpx

from ..core.config import settings

logger = logging.getLogger(__name__)

SUCCESS_CODE = 10000
TOKEN_ERROR_CODES = {10005, 10006, 10007}
_ALLOWED_HOST_SUFFIX = ".fangxinqian.cn"


class FxqCaError(Exception):
    """放心签调用错误（消息不携带敏感请求/响应正文）。"""

    def __init__(self, message: str, *, code: int | None = None, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class FxqResponse:
    code: int
    data: Any
    msg: str
    trade_no: str | None = None


def _is_official_https(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (host == "fangxinqian.cn" or host.endswith(_ALLOWED_HOST_SUFFIX))


def _is_provider_file_https(url: str) -> bool:
    """签署接口只允许从放心签官方域名或阿里云 OSS HTTPS 地址取回文件。"""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    return parsed.scheme == "https" and (
        host == "fangxinqian.cn"
        or host.endswith(_ALLOWED_HOST_SUFFIX)
        or host.endswith(".aliyuncs.com")
    )


def config_errors(config=settings) -> list[str]:
    """返回可安全展示的配置缺失项，不回显任何密钥值。"""
    sign_enabled = bool(getattr(config, "FXQ_DOCUMENT_SIGN_ENABLED", False))
    if not config.FXQ_CA_ENABLED and not config.FXQ_CA_REQUIRED and not sign_enabled:
        return []
    errors: list[str] = []
    if not config.FXQ_CA_ENABLED and (config.FXQ_CA_REQUIRED or sign_enabled):
        errors.append("启用放心签签署/生产门禁时必须设置 FXQ_CA_ENABLED=true")
    if config.FXQ_CA_REQUIRED and not sign_enabled:
        errors.append("FXQ_CA_REQUIRED=true 时必须启用 FXQ_DOCUMENT_SIGN_ENABLED")
    if not config.FXQ_APP_KEY:
        errors.append("FXQ_APP_KEY 未配置")
    if not config.FXQ_APP_SECRET:
        errors.append("FXQ_APP_SECRET 未配置")
    if not config.FXQ_CA_REDIRECT_URL:
        errors.append("FXQ_CA_REDIRECT_URL 未配置")
    elif not config.FXQ_CA_REDIRECT_URL.startswith("https://"):
        errors.append("FXQ_CA_REDIRECT_URL 必须使用 HTTPS")
    url_fields = ["FXQ_TOKEN_URL", "FXQ_REQUEST_SIGN_URL", "FXQ_CA_AGREEMENT_URL", "FXQ_CA_RESULT_URL"]
    if sign_enabled:
        if not getattr(config, "FXQ_COMPANY_NAME", ""):
            errors.append("FXQ_COMPANY_NAME 未配置")
        if not getattr(config, "FXQ_COMPANY_IDNO", ""):
            errors.append("FXQ_COMPANY_IDNO 未配置")
        url_fields.extend(
            ["FXQ_PERSONAL_SEAL_URL", "FXQ_COMPANY_SEAL_URL", "FXQ_PDF_SIGN_URL", "FXQ_PDF_VERIFY_URL"]
        )
    for field in url_fields:
        if not _is_official_https(getattr(config, field, "")):
            errors.append(f"{field} 必须是放心签官方 HTTPS 地址")
    return errors


class FxqCaClient:
    """可注入 MockTransport 的异步客户端，生产默认只访问放心签官方 HTTPS 域名。"""

    def __init__(self, *, config=settings, transport: httpx.AsyncBaseTransport | None = None):
        self.config = config
        self.transport = transport
        self._token: str | None = None
        self._token_expires_monotonic = 0.0
        self._token_lock = asyncio.Lock()

    def ensure_ready(self) -> None:
        if not self.config.FXQ_CA_ENABLED:
            raise FxqCaError("FXQ_CA_ENABLED 未开启")
        errors = config_errors(self.config)
        if errors:
            raise FxqCaError("；".join(errors))

    async def _post(self, url: str, *, payload: dict, headers: dict[str, str] | None = None) -> dict:
        try:
            async with httpx.AsyncClient(
                timeout=self.config.FXQ_HTTP_TIMEOUT_SECONDS,
                transport=self.transport,
                follow_redirects=False,
            ) as client:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                body = response.json()
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise FxqCaError("放心签网络暂时不可用", retryable=True) from exc
        except httpx.HTTPStatusError as exc:
            retryable = exc.response.status_code >= 500
            raise FxqCaError("放心签 HTTP 调用失败", retryable=retryable) from exc
        except (TypeError, ValueError) as exc:
            raise FxqCaError("放心签返回了无法解析的数据") from exc
        if not isinstance(body, dict):
            raise FxqCaError("放心签返回格式不正确")
        return body

    @staticmethod
    def _provider_code(body: dict) -> int | None:
        try:
            return int(body.get("code"))
        except (TypeError, ValueError):
            return None

    async def _get_token(self, *, force: bool = False) -> str:
        self.ensure_ready()
        if not force and self._token and time.monotonic() < self._token_expires_monotonic:
            return self._token
        async with self._token_lock:
            if not force and self._token and time.monotonic() < self._token_expires_monotonic:
                return self._token
            body = await self._post(
                self.config.FXQ_TOKEN_URL,
                payload={"key": self.config.FXQ_APP_KEY, "secret": self.config.FXQ_APP_SECRET},
            )
            code = self._provider_code(body)
            token = body.get("data")
            if code != SUCCESS_CODE or not isinstance(token, str) or not token:
                raise FxqCaError("放心签 token 获取失败", code=code)
            self._token = token
            # 标准 API 文档声明 token 有效期 2 小时；提前 10 分钟刷新。
            self._token_expires_monotonic = time.monotonic() + 110 * 60
            return token

    async def check_auth(self) -> None:
        """只验证应用凭据能否换取 token；不打印也不返回 token。"""
        await self._get_token(force=True)

    async def _signed_post(self, url: str, payload: dict) -> FxqResponse:
        self.ensure_ready()
        for attempt in range(2):
            token = await self._get_token(force=attempt > 0)
            encrypted = await self._post(
                self.config.FXQ_REQUEST_SIGN_URL,
                payload=payload,
                headers={"token": token, "Content-Type": "application/json"},
            )
            encrypt_code = self._provider_code(encrypted)
            sign_data = encrypted.get("data") if isinstance(encrypted.get("data"), dict) else {}
            nonce, sign = sign_data.get("nonce"), sign_data.get("sign")
            if encrypt_code != SUCCESS_CODE or not nonce or not sign:
                if encrypt_code in TOKEN_ERROR_CODES and attempt == 0:
                    continue
                raise FxqCaError("放心签请求签名生成失败", code=encrypt_code)

            body = await self._post(
                url,
                payload=payload,
                headers={
                    "token": token,
                    "fxq-nonce": str(nonce),
                    "fxq-sign": str(sign),
                    "Content-Type": "application/json",
                },
            )
            code = self._provider_code(body)
            if code in TOKEN_ERROR_CODES and attempt == 0:
                self._token = None
                continue
            if code != SUCCESS_CODE:
                msg = str(body.get("msg") or "业务请求失败")[:120]
                raise FxqCaError(
                    f"放心签业务请求失败：{msg}",
                    code=code,
                    retryable=code in {1506, 9999, 99999},
                )
            data = body.get("data")
            if data is None:
                raise FxqCaError("放心签业务响应缺少 data", code=code)
            return FxqResponse(
                code=code,
                data=data,
                msg=str(body.get("msg") or "")[:120],
                trade_no=str(body.get("tradeNo"))[:64] if body.get("tradeNo") else None,
            )
        raise FxqCaError("放心签 token 刷新后仍不可用")

    async def start_agreement(
        self, *, name: str, id_no: str, redirect_url: str, user_id: str, order_no: str
    ) -> FxqResponse:
        result = await self._signed_post(
            self.config.FXQ_CA_AGREEMENT_URL,
            {
                "name": name,
                "idNo": id_no,
                "redirectUrl": redirect_url,
                "userId": user_id,
                "orderNo": order_no,
            },
        )
        if not isinstance(result.data, dict):
            raise FxqCaError("放心签双录响应 data 格式不正确", code=result.code)
        return result

    async def query_result(self, *, order_no: str) -> FxqResponse:
        # 文档说明 getFile 不传时默认返回照片；显式传 0，避免把生物识别材料拉回业务系统。
        result = await self._signed_post(
            self.config.FXQ_CA_RESULT_URL,
            {"orderNo": order_no, "getFile": "0", "getDetails": "1", "getPhotos": "0"},
        )
        if not isinstance(result.data, dict):
            raise FxqCaError("放心签核身响应 data 格式不正确", code=result.code)
        return result

    async def generate_personal_seal(self, *, name: str) -> FxqResponse:
        result = await self._signed_post(
            self.config.FXQ_PERSONAL_SEAL_URL,
            {
                "name": name,
                "rtype": 1,
                "color": 0,
                "font": 1,
                "type": 0,
                "isAddType": 1,
                "chooseAddFont": 0,
            },
        )
        if not isinstance(result.data, str) or not _is_provider_file_https(result.data):
            raise FxqCaError("放心签个人签章返回地址不安全或格式不正确", code=result.code)
        return result

    async def generate_company_seal(self, *, name: str) -> FxqResponse:
        result = await self._signed_post(
            self.config.FXQ_COMPANY_SEAL_URL,
            {
                "name": name,
                "title": "处方专用章",
                "type": 0,
                "color": 0,
                "font": 0,
                "rtype": 1,
                "isRound": 2,
            },
        )
        if not isinstance(result.data, str) or not _is_provider_file_https(result.data):
            raise FxqCaError("放心签企业签章返回地址不安全或格式不正确", code=result.code)
        return result

    async def sign_pdf(self, *, contract_base64: str, signers: list[dict[str, Any]]) -> FxqResponse:
        result = await self._signed_post(
            self.config.FXQ_PDF_SIGN_URL,
            {
                "contract": contract_base64,
                "type": 1,
                "size": 90,
                "signers": signers,
            },
        )
        if not isinstance(result.data, str) or not _is_provider_file_https(result.data):
            raise FxqCaError("放心签签后文件地址不安全或格式不正确", code=result.code)
        return result

    async def verify_pdf(self, *, file_url: str) -> FxqResponse:
        if not _is_provider_file_https(file_url):
            raise FxqCaError("拒绝验签非放心签/OSS HTTPS 文件地址")
        result = await self._signed_post(
            self.config.FXQ_PDF_VERIFY_URL,
            {"fileUrl": file_url, "fileSuffix": "pdf"},
        )
        if not isinstance(result.data, dict):
            raise FxqCaError("放心签验签响应 data 格式不正确", code=result.code)
        return result

    async def download_pdf(self, *, file_url: str) -> bytes:
        """下载刚签署的 PDF；不跟随跳转并限制大小，避免 SSRF 与内存放大。"""
        if not _is_provider_file_https(file_url):
            raise FxqCaError("拒绝下载非放心签/OSS HTTPS 文件地址")
        limit = int(getattr(self.config, "FXQ_MAX_PDF_BYTES", 10 * 1024 * 1024))
        try:
            async with httpx.AsyncClient(
                timeout=self.config.FXQ_HTTP_TIMEOUT_SECONDS,
                transport=self.transport,
                follow_redirects=False,
            ) as client:
                async with client.stream("GET", file_url) as response:
                    response.raise_for_status()
                    chunks: list[bytes] = []
                    size = 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > limit:
                            raise FxqCaError("放心签签后 PDF 超过大小限制")
                        chunks.append(chunk)
        except FxqCaError:
            raise
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise FxqCaError("放心签签后 PDF 下载暂时不可用", retryable=True) from exc
        except httpx.HTTPStatusError as exc:
            raise FxqCaError(
                "放心签签后 PDF 下载失败",
                retryable=exc.response.status_code >= 500,
            ) from exc
        data = b"".join(chunks)
        if not data.startswith(b"%PDF-"):
            raise FxqCaError("放心签返回的签后文件不是有效 PDF")
        return data


fxq_ca_client = FxqCaClient()
