"""天津监管平台连通性自检脚本（S0 验收用，独立运行，不依赖业务代码）。

用法：
    pip install gmssl httpx
    修改下方 GATEWAY / APP_KEY / APP_SECRET / UNIT_ID / ORGAN_ID 后：
    python scripts/tj_ping.py

流程：
    1. 本地国密自检：与官方 SDK 生成的黄金向量对拍（见 docs/tianjin_gateway_protocol.md）
    2. 真实调用 uploadDrugCatalogue 推送 1 条演示药品
判读：
    body.msgCode=200            → 全链路通（密钥/白名单/加密/签名全部正确）
    code=40007                  → IP 不在白名单
    code=40004 / 40010          → 密钥或签名问题（先确认 appSecret 是 32 位 hex）
    body.msgCode=-99            → 链路已通，仅业务字段缺失（msg 会列字段名）
"""
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # backend/
from app.utils.sm_crypto import (  # noqa: E402
    build_sign_headers,
    sm3_hex_upper,
    sm4_cbc_encrypt_hex,
)

# ======== 以下 5 项按平台"秘钥生成及管理"页填写 ========
GATEWAY = "http://imssp.wsjk.tj.gov.cn/net-diag-service/test-openapi/api"  # 测试网关，以平台页面为准
APP_KEY = "<测试环境appKey>"
APP_SECRET = "<测试环境appSecret，应为32位hex>"
UNIT_ID = "<监管平台机构ID>"
ORGAN_ID = "<全国统一组织机构代码>"
ORGAN_NAME = "天津逑贝互联网医院"
# =====================================================


def call(method: str, payload) -> None:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    enc = sm4_cbc_encrypt_hex(body, APP_SECRET)
    headers = build_sign_headers(method, sm3_hex_upper(enc), APP_KEY)
    print(f"→ POST {GATEWAY}  method={method}")
    r = httpx.post(GATEWAY, content=enc, headers=headers, timeout=30)
    print(f"← HTTP {r.status_code}: {r.text}")


def self_check() -> None:
    """黄金向量对拍（来源：官方 jar，docs/tianjin_gateway_protocol.md 第二节）。

    完整向量断言见 tests/test_tj_gateway.py；此处抽 3 条关键向量做发送前自检。
    """
    demo_secret = "bbf1dd188b8b4629853f06f118d11e4a"
    assert sm3_hex_upper("abc") == (
        "66C7F0F462EEEDD9D1F2D46BDC10E4E24167C4875CF2F7A2297DA02B8F4BA8E0"
    ), "SM3 与国标不符"
    assert sm4_cbc_encrypt_hex("[1]", demo_secret) == (
        "49a9a1cb6403aa7ca5d7be3287b0dc6b"
    ), "SM4-CBC 与 SDK 不符（填充应为 ISO7816-4，非 PKCS7）"
    headers = build_sign_headers(
        "uploadDrugCatalogue",
        "F7DCA75A3D6083A0E4FD0BA219FFE8AC10E35AE45FD8A91F90A9CDAB5A0ED056",
        "ngari5fd5ad2196834aa7",
        nonce="8d708068-0a36-47d3-8ff4-011fdace7d63",
        timestamp_ms="1718185594026",
    )
    assert headers["X-Ca-Signature"] == (
        "A07C0B67CE2996DF9416A5BE7EB7F4E8EAF40F31D46423A1FA9ECEA188C7627A"
    ), "签名串组装与 SDK 不符"
    print("本地国密自检通过（SM3/SM4/签名 与官方 SDK 一致）")


if __name__ == "__main__":
    self_check()
    call(
        "uploadDrugCatalogue",
        [
            {
                "organID": ORGAN_ID,
                "unitID": UNIT_ID,
                "organName": ORGAN_NAME,
                "drugClass": "010101",  # 青霉素类（药品分类代码字典 3.10）
                "hospDrcode": "PING-TEST-001",
                "hospDrugName": "阿莫西林胶囊",
                "hospDrugPacking": "0.25g*24粒",
                "hospDrugManuf": "联调测试数据",
                "drugPrice": 10.80,
                "useFlag": "2",  # 直接传"取消"，避免测试数据污染目录
                "updateTime": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        ],
    )
