"""天津监管网关国密实现黄金向量对拍（docs/tianjin_gateway_protocol.md 第二节 V1–V7）。

向量由官方 SDK ngari-supervision-1.7-SNAPSHOT.jar 本体生成，必须逐字节一致。
本文件只依赖 gmssl（不拉起 FastAPI），`pytest tests/test_tj_gateway.py` 可独立运行。
"""
from app.utils.sm_crypto import (
    build_sign_headers,
    sm3_hex_upper,
    sm4_cbc_decrypt,
    sm4_cbc_encrypt_hex,
)

DEMO_SECRET = "bbf1dd188b8b4629853f06f118d11e4a"  # jar 内置演示密钥


def test_v1_sm3_standard_vector():
    """SM3('abc') 与 GB/T 32905 标准向量一致，输出大写 hex。"""
    assert sm3_hex_upper("abc") == (
        "66C7F0F462EEEDD9D1F2D46BDC10E4E24167C4875CF2F7A2297DA02B8F4BA8E0"
    )


def test_v2_sm4_cbc_single_block():
    """SM4-CBC('[1]')：固定 IV + PKCS7 + 小写 hex 输出。"""
    assert sm4_cbc_encrypt_hex("[1]", DEMO_SECRET) == "49a9a1cb6403aa7ca5d7be3287b0dc6b"


def test_v3_sm4_cbc_chinese_payload():
    """含中文业务体的多块加密。"""
    body = '[{"organID":"12345678901234567X","unitID":"U0001","organName":"天津逑贝互联网医院"}]'
    assert sm4_cbc_encrypt_hex(body, DEMO_SECRET) == (
        "bda12c065d493fcb45851a847d58648fdcb5dc17fc8c2f895ad2e2394bfdc309"
        "c977b99228aa51fa2aeabe25d28af20bf7658673dc1f8a2c9e7ab7de50311bdf"
        "ba0d8a0c84ad3dd9a41c1635ec80d121fa0b5ef611139a6d23c4644480fb68a6"
    )


def test_v8_v9_block_boundary_padding():
    """ISO7816-4 填充：明文恰为整块时新增一个填充块（16B 明文 → 32B 密文）。"""
    assert sm4_cbc_encrypt_hex("0123456789abcdef", DEMO_SECRET) == (
        "a9f4a4c761cf5110a2adbd8e1cdb79b025db47d12e40bf0803278053400e9f40"
    )
    assert sm4_cbc_encrypt_hex("0123456789abcdef0123456789abcdef", DEMO_SECRET) == (
        "a9f4a4c761cf5110a2adbd8e1cdb79b0d0cdb4c80a112f917302699a23c67f4c"
        "74e73fb22408c9dbe2acab3ed307ecb8"
    )


def test_sm4_roundtrip():
    body = '[{"k":"值——含标点、emoji🏥"}]'
    enc = sm4_cbc_encrypt_hex(body, DEMO_SECRET)
    assert sm4_cbc_decrypt(enc, DEMO_SECRET) == body


def test_v4_content_md5_is_sm3_of_cipher():
    enc = sm4_cbc_encrypt_hex("[1]", DEMO_SECRET)
    assert sm3_hex_upper(enc) == (
        "F7DCA75A3D6083A0E4FD0BA219FFE8AC10E35AE45FD8A91F90A9CDAB5A0ED056"
    )


def test_v5_v6_v7_signature_headers():
    """签名串字典序拼装、SM3 签名、Signature-Headers 与 SDK 一致。"""
    headers = build_sign_headers(
        "uploadDrugCatalogue",
        "F7DCA75A3D6083A0E4FD0BA219FFE8AC10E35AE45FD8A91F90A9CDAB5A0ED056",
        "ngari5fd5ad2196834aa7",
        nonce="8d708068-0a36-47d3-8ff4-011fdace7d63",
        timestamp_ms="1718185594026",
    )
    # V6：签名
    assert headers["X-Ca-Signature"] == (
        "A07C0B67CE2996DF9416A5BE7EB7F4E8EAF40F31D46423A1FA9ECEA188C7627A"
    )
    # V7：参与签名头（小写、字典序、逗号连接）
    assert headers["X-Ca-Signature-Headers"] == (
        "x-ca-key,x-ca-nonce,x-ca-timestamp,x-content-md5,x-service-id,x-service-method"
    )
    # 固定头
    assert headers["X-Service-Id"] == "his.provinceDataUploadService"
    assert headers["Content-Type"] == "application/json"
