"""微信支付 V3：JSAPI 下单 + 回调验签解密（M2 / 解锁 pending #3）。

设计与 auth_service 一致：**凭据未配齐时回退 mock**，保证本地联调不受阻；
配齐后自动走真实微信支付。真实模式所需 .env：
  WX_APPID / WX_MCHID / WX_API_V3_KEY / WX_MCH_CERT_SERIAL /
  WX_MCH_PRIVATE_KEY_PATH（商户私钥 apiclient_key.pem）/
  WX_PAY_NOTIFY_URL（公网 HTTPS 回调地址）。

签名规范见微信支付 V3 文档：
  - 请求签名：METHOD\\nURL\\nTIMESTAMP\\nNONCE\\nBODY\\n，商户私钥 RSA-SHA256
  - 回调验签：TIMESTAMP\\nNONCE\\nBODY\\n，平台证书公钥 RSA-SHA256
  - 敏感信息：AEAD_AES_256_GCM，密钥为 APIv3 密钥
"""
import json
import logging
import time
import uuid
from base64 import b64decode, b64encode
from functools import lru_cache
from pathlib import Path

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.x509 import load_pem_x509_certificate

from ..core.config import settings
from ..schemas.order import PrepayOut

logger = logging.getLogger("pay")

API_BASE = "https://api.mch.weixin.qq.com"
DRUG_SUFFIX = "-DRUG"  # 药费支付的 out_trade_no 后缀（与挂号费区分，同一订单两笔支付）


class PayError(Exception):
    """微信支付下单 / 验签 / 解密失败。"""


def is_enabled() -> bool:
    """凭据是否配齐（含公网回调地址）。未配齐则各接口回退 mock。"""
    return bool(
        settings.WX_APPID
        and settings.WX_MCHID
        and settings.WX_API_V3_KEY
        and settings.WX_MCH_CERT_SERIAL
        and settings.WX_MCH_PRIVATE_KEY_PATH
        and settings.WX_PAY_NOTIFY_URL
        and _key_path().exists()
    )


# ——————————————————— 商户私钥 / 请求签名 ———————————————————

def _key_path() -> Path:
    p = Path(settings.WX_MCH_PRIVATE_KEY_PATH or "")
    if p and not p.is_absolute():
        p = Path(__file__).resolve().parents[2] / p  # 相对 backend/ 根
    return p


@lru_cache(maxsize=1)
def _private_key():
    return serialization.load_pem_private_key(_key_path().read_bytes(), password=None)


def _sign(message: str) -> str:
    sig = _private_key().sign(message.encode(), padding.PKCS1v15(), hashes.SHA256())
    return b64encode(sig).decode()


def _auth_header(method: str, url_path: str, body: str) -> str:
    ts = str(int(time.time()))
    nonce = uuid.uuid4().hex
    signature = _sign(f"{method}\n{url_path}\n{ts}\n{nonce}\n{body}\n")
    return (
        f'WECHATPAY2-SHA256-RSA2048 mchid="{settings.WX_MCHID}",'
        f'nonce_str="{nonce}",signature="{signature}",timestamp="{ts}",'
        f'serial_no="{settings.WX_MCH_CERT_SERIAL}"'
    )


async def _post(url_path: str, payload: dict) -> dict:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    headers = {
        "Authorization": _auth_header("POST", url_path, body),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(API_BASE + url_path, content=body.encode(), headers=headers)
    if r.status_code not in (200, 204):
        logger.error("微信支付请求失败 %s %s: %s", url_path, r.status_code, r.text)
        raise PayError(f"微信支付请求失败: {r.text}")
    return r.json() if r.content else {}


async def _get(url_path: str) -> dict:
    headers = {"Authorization": _auth_header("GET", url_path, ""), "Accept": "application/json"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(API_BASE + url_path, headers=headers)
    if r.status_code != 200:
        raise PayError(f"微信支付请求失败: {r.text}")
    return r.json()


# ——————————————————— JSAPI 下单 ———————————————————

async def prepay(order_no: str, fee_fen: int, openid: str, description: str, order_id: int) -> PrepayOut:
    """JSAPI 下单，返回 wx.requestPayment 五元组。未启用真实支付则回退 mock。"""
    if not is_enabled():
        return _mock_prepay(order_id)
    if not openid:
        raise PayError("缺少支付者 openid")
    data = await _post("/v3/pay/transactions/jsapi", {
        "appid": settings.WX_APPID,
        "mchid": settings.WX_MCHID,
        "description": description,
        "out_trade_no": order_no,
        "notify_url": settings.WX_PAY_NOTIFY_URL,
        "amount": {"total": fee_fen, "currency": "CNY"},
        "payer": {"openid": openid},
    })
    return _build_pay_params(data["prepay_id"], order_id)


def _build_pay_params(prepay_id: str, order_id: int) -> PrepayOut:
    """小程序调起支付参数：对 appId\\ntimeStamp\\nnonceStr\\npackage\\n 用商户私钥签名。"""
    ts = str(int(time.time()))
    nonce = uuid.uuid4().hex
    package = f"prepay_id={prepay_id}"
    pay_sign = _sign(f"{settings.WX_APPID}\n{ts}\n{nonce}\n{package}\n")
    return PrepayOut(
        timeStamp=ts, nonceStr=nonce, package=package,
        signType="RSA", paySign=pay_sign, order_id=order_id,
    )


def _mock_prepay(order_id: int) -> PrepayOut:
    """开发回退：假五元组（前端走 /pay/mock 直接置成功）。"""
    return PrepayOut(
        timeStamp=str(int(time.time())), nonceStr=uuid.uuid4().hex,
        package="prepay_id=mock_" + uuid.uuid4().hex[:12],
        signType="RSA", paySign="MOCK_SIGN", order_id=order_id,
    )


# ——————————————————— 回调验签 + 解密 ———————————————————

_platform_certs: dict[str, object] = {}  # serial_no -> x509 证书（缓存）


def _aes_gcm_decrypt(nonce: str, ciphertext: str, associated_data: str) -> bytes:
    """APIv3 密钥 AEAD_AES_256_GCM 解密（密文 base64 含 16B tag）。"""
    aes = AESGCM(settings.WX_API_V3_KEY.encode())
    aad = associated_data.encode() if associated_data else None
    return aes.decrypt(nonce.encode(), b64decode(ciphertext), aad)


async def _refresh_platform_certs() -> None:
    """拉取并解密微信支付平台证书，按序列号缓存（用于回调验签）。"""
    data = await _get("/v3/certificates")
    for item in data.get("data", []):
        enc = item["encrypt_certificate"]
        pem = _aes_gcm_decrypt(enc["nonce"], enc["ciphertext"], enc.get("associated_data", ""))
        _platform_certs[item["serial_no"]] = load_pem_x509_certificate(pem)


async def _verify(headers, body: str) -> None:
    serial = headers.get("Wechatpay-Serial")
    timestamp = headers.get("Wechatpay-Timestamp")
    nonce = headers.get("Wechatpay-Nonce")
    signature = headers.get("Wechatpay-Signature")
    if not all([serial, timestamp, nonce, signature]):
        raise PayError("回调缺少签名头")
    cert = _platform_certs.get(serial)
    if cert is None:
        await _refresh_platform_certs()  # 证书轮换：未命中则刷新一次
        cert = _platform_certs.get(serial)
    if cert is None:
        raise PayError("未找到对应平台证书")
    msg = f"{timestamp}\n{nonce}\n{body}\n".encode()
    try:
        cert.public_key().verify(b64decode(signature), msg, padding.PKCS1v15(), hashes.SHA256())
    except Exception as e:  # noqa: BLE001 验签失败
        raise PayError("回调验签失败") from e


async def verify_and_decrypt(headers, body: str) -> dict:
    """验签 + 解密回调，返回明文交易信息（含 out_trade_no / trade_state / amount）。"""
    await _verify(headers, body)
    res = json.loads(body)["resource"]
    plain = _aes_gcm_decrypt(res["nonce"], res["ciphertext"], res.get("associated_data", ""))
    return json.loads(plain)
