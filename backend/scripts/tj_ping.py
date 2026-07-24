"""天津监管平台连通性自检脚本（S0 验收用，独立运行，不依赖业务代码）。

用法：
    pip install gmssl httpx
    配置优先从环境变量 / backend/.env 读取（TJ_GATEWAY_URL 等 6 项，密钥勿写进本文件），
    也可临时修改下方常量兜底：
    python scripts/tj_ping.py --self-check-only
    python scripts/tj_ping.py                         # 测试环境发送 1 条取消态目录数据
    python scripts/tj_ping.py --allow-production-write  # 正式环境仅在明确批准后允许写入

流程：
    1. 本地国密自检：与官方 SDK 生成的黄金向量对拍（见 docs/tianjin_gateway_protocol.md）
    2. 真实调用 uploadDrugCatalogue 推送 1 条演示药品
判读：
    body.msgCode=200            → 全链路通（密钥/白名单/加密/签名全部正确）
    code=40007                  → IP 不在白名单
    code=40004 / 40010          → 密钥或签名问题（先确认 appSecret 是 32 位 hex）
    body.msgCode=-99            → 链路已通，仅业务字段缺失（msg 会列字段名）
"""
import argparse
import json
import os
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
from app.services.tj_config import gateway_config_errors, is_production_gateway  # noqa: E402


def _load_dotenv() -> None:
    """轻量读取 backend/.env（不引入依赖；已有环境变量优先）。"""
    env = Path(__file__).resolve().parent.parent / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

# ======== 配置：环境变量 / backend/.env 优先（TJ_*），常量仅作兜底 ========
GATEWAY = os.environ.get("TJ_GATEWAY_URL") or "https://imssp.wsjk.tj.gov.cn/net-diag-service/test-openapi/api"
APP_KEY = os.environ.get("TJ_APP_KEY") or "<测试环境appKey>"
APP_SECRET = os.environ.get("TJ_APP_SECRET") or "<测试环境appSecret，应为32位hex>"
UNIT_ID = os.environ.get("TJ_UNIT_ID") or "<监管平台机构ID>"
ORGAN_ID = os.environ.get("ORGAN_ID") or "<全国统一组织机构代码>"
ORGAN_NAME = os.environ.get("ORGAN_NAME") or "天津逑贝互联网医院"
# ========================================================================


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
    parser = argparse.ArgumentParser(description="天津监管平台连通性自检")
    parser.add_argument("--self-check-only", action="store_true", help="只做本地国密自检，不发网络请求")
    parser.add_argument(
        "--allow-production-write", action="store_true",
        help="明确允许向正式网关写入一条取消态目录记录（通常应改用真实药品目录初始化）",
    )
    args = parser.parse_args()
    self_check()
    if args.self_check_only:
        print("已按 --self-check-only 停止，未发网络请求。")
        raise SystemExit(0)
    config = type("PingConfig", (), {
        "TJ_GATEWAY_URL": GATEWAY,
        "TJ_APP_KEY": APP_KEY,
        "TJ_APP_SECRET": APP_SECRET,
        "TJ_UNIT_ID": UNIT_ID,
        "ORGAN_ID": ORGAN_ID,
        "ORGAN_NAME": ORGAN_NAME,
    })()
    errors = gateway_config_errors(config)
    if errors:
        for error in errors:
            print(f"配置错误：{error}")
        raise SystemExit(2)
    if is_production_gateway(GATEWAY) and not args.allow_production_write:
        print("拒绝向正式网关写入演示药品。正式连通性请通过真实药品目录首批上报验证；")
        print("如确需写入取消态探针，必须显式添加 --allow-production-write。")
        raise SystemExit(2)
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
