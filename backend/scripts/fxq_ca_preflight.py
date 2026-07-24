"""放心签高级证书接口上线前检查。

默认只做本地配置检查；加 --live 后仅验证 AppKey/AppSecret 能否换取 token，
不创建双录订单、不消耗核验次数，也不会打印 token 或密钥。

用法：
  python -m scripts.fxq_ca_preflight
  python -m scripts.fxq_ca_preflight --live
"""
import argparse
import asyncio

from app.core.config import settings
from app.services.fxq_ca import FxqCaError, config_errors, fxq_ca_client


async def main(live: bool) -> int:
    errors = config_errors(settings)
    if not settings.FXQ_CA_ENABLED:
        errors.insert(0, "FXQ_CA_ENABLED 未开启")
    if errors:
        for error in errors:
            print(f"FAIL {error}")
        return 1
    print("OK 放心签配置字段与官方域名检查通过")
    if not live:
        print("SKIP 未请求外网；加 --live 可验证 token")
        return 0
    try:
        await fxq_ca_client.check_auth()
    except FxqCaError as exc:
        print(f"FAIL token 验证失败：{exc}")
        return 2
    print("OK AppKey/AppSecret 换取 token 成功（token 未输出）")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="真实请求放心签 token 接口")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.live)))
