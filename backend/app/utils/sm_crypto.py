"""天津监管平台国密工具（SM4-CBC 加密 / SM3 摘要 / 请求头签名）。

协议依据：docs/tianjin_gateway_protocol.md（官方 SDK ngari-supervision jar 逆向确认版）。
要点（与规范 PDF 文字描述不同，以 SDK 为准）：
  - SM4-CBC：key = hex 解码的 appSecret（32 hex → 16 字节），IV 固定常量，
    填充为 **ISO/IEC 7816-4**（0x80 后补 0x00；明文恰为整块时新增一个填充块），
    密文输出【小写 hex 字符串】（非 Base64）——注意不是 PKCS7，gmssl 的
    crypt_cbc 自带 PKCS7 填充不可直接用，故此处手写 CBC 链；
  - X-Content-MD5 名为 MD5，实为 SM3(密文串)，输出【大写 hex】；
  - 签名串 = 参与签名的头按 key 字典序，每项 "小写头名:值"，用 "&" 连接，再 SM3；
    requestBody 不直接参与签名（经 X-Content-MD5 间接绑定）。

本模块只依赖 gmssl，保持纯函数，便于离线单测（tests/test_tj_gateway.py 黄金向量对拍）。
"""
import time
import uuid

from gmssl import func, sm3
from gmssl.sm4 import SM4_DECRYPT, SM4_ENCRYPT, CryptSM4

# SDK 硬编码的固定 IV（openapi.util.SM4Utils）
TJ_FIXED_IV_HEX = "abcd0863ef9087ced675985321bedf67"

SERVICE_ID = "his.provinceDataUploadService"

_BLOCK = 16


def sm3_hex_upper(s: str) -> str:
    """SM3 摘要，大写 hex（对齐 SDK SM3Util.encode 输出）。"""
    return sm3.sm3_hash(func.bytes_to_list(s.encode("utf-8"))).upper()


def _iso7816_pad(data: bytes) -> bytes:
    pad_len = _BLOCK - (len(data) % _BLOCK)
    return data + b"\x80" + b"\x00" * (pad_len - 1)


def _iso7816_unpad(data: bytes) -> bytes:
    trimmed = data.rstrip(b"\x00")
    if not trimmed or trimmed[-1] != 0x80:
        raise ValueError("非法的 ISO7816-4 填充")
    return trimmed[:-1]


def _sm4_blocks(key_hex: str, mode: int):
    c = CryptSM4()
    c.set_key(bytes.fromhex(key_hex), mode)
    return c


def sm4_cbc_encrypt_hex(plaintext: str, app_secret_hex: str) -> str:
    """SM4-CBC 加密：明文 UTF-8 → 小写 hex 密文（对齐 SDK encryptNationalSerAlgorithmCBC）。"""
    c = _sm4_blocks(app_secret_hex, SM4_ENCRYPT)
    data = _iso7816_pad(plaintext.encode("utf-8"))
    prev = bytes.fromhex(TJ_FIXED_IV_HEX)
    out = bytearray()
    for i in range(0, len(data), _BLOCK):
        block = bytes(x ^ y for x, y in zip(data[i : i + _BLOCK], prev))
        prev = bytes(c.one_round(c.sk, func.bytes_to_list(block)))
        out += prev
    return out.hex()


def sm4_cbc_decrypt(cipher_hex: str, app_secret_hex: str) -> str:
    """SM4-CBC 解密（调试/回环测试用）。"""
    c = _sm4_blocks(app_secret_hex, SM4_DECRYPT)
    data = bytes.fromhex(cipher_hex)
    prev = bytes.fromhex(TJ_FIXED_IV_HEX)
    out = bytearray()
    for i in range(0, len(data), _BLOCK):
        block = data[i : i + _BLOCK]
        dec = bytes(c.one_round(c.sk, func.bytes_to_list(block)))
        out += bytes(x ^ y for x, y in zip(dec, prev))
        prev = block
    return _iso7816_unpad(bytes(out)).decode("utf-8")


def build_sign_headers(
    method: str,
    content_digest: str,
    app_key: str,
    *,
    nonce: str | None = None,
    timestamp_ms: str | None = None,
) -> dict[str, str]:
    """组装带签名的完整请求头。

    content_digest：请求体摘要（加密接口 = SM3(密文串)；uploadFile 明文接口 = SM3(明文串)）。
    nonce / timestamp_ms 仅测试时传入固定值做对拍。
    """
    headers = {
        "X-Service-Id": SERVICE_ID,
        "X-Service-Method": method,
        "X-Ca-Key": app_key,
        "X-Ca-Nonce": nonce or str(uuid.uuid4()),
        "X-Ca-Timestamp": timestamp_ms or str(int(time.time() * 1000)),
        "X-Content-MD5": content_digest,
    }
    items = sorted((k.lower(), v) for k, v in headers.items())
    sign_str = "&".join(f"{k}:{v}" for k, v in items)
    headers["X-Ca-Signature"] = sm3_hex_upper(sign_str)
    headers["X-Ca-Signature-Headers"] = ",".join(k for k, _ in items)
    headers["Content-Type"] = "application/json"
    return headers
