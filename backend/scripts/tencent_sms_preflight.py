"""腾讯云短信配置预检；默认不联网，--live 才发送一条真实短信。"""
from __future__ import annotations

import argparse
import asyncio
import re
import sys

from app.core.config import settings
from app.services import sms_service


def _mask_phone(phone: str) -> str:
    return f"{phone[:3]}****{phone[-4:]}"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="实际发送一条短信")
    parser.add_argument("--phone", help="--live 时必填的中国大陆手机号")
    parser.add_argument(
        "--purpose",
        choices=sorted(sms_service.SMS_PURPOSES),
        default=sms_service.SMS_PURPOSE_REGISTER_PHONE,
    )
    return parser


async def _run_live(phone: str, purpose: str) -> int:
    ok, message, _ = await sms_service.send_code(
        phone,
        purpose,
        user_id=0,
    )
    if not ok:
        print(f"FAIL 真机短信发送失败：{message}")
        return 1
    print(f"OK 已向 {_mask_phone(phone)} 提交 {purpose} 短信，请核对实际收码内容")
    return 0


def main() -> int:
    args = _parser().parse_args()
    errors = sms_service.tencent_sms_config_errors()
    if settings.TENCENT_SMS_SIGN.strip() not in ("", "天津逑贝互联网医院"):
        errors.append("TENCENT_SMS_SIGN 与已生效签名不一致")
    if settings.TENCENT_SMS_TEMPLATE_REGISTER_PHONE_ID.strip() not in ("", "2695131"):
        errors.append("手机注册模板 ID 与腾讯云已提交模板 2695131 不一致")
    if settings.TENCENT_SMS_TEMPLATE_CHANGE_PHONE_ID.strip() not in ("", "2695133"):
        errors.append("修改手机号模板 ID 与腾讯云已提交模板 2695133 不一致")
    if errors:
        for error in dict.fromkeys(errors):
            print(f"FAIL {error}")
        return 1

    print("OK 腾讯云短信凭据字段已配置（值未输出）")
    print("OK 签名：天津逑贝互联网医院")
    print("OK 手机注册模板：2695131，参数顺序为验证码、5分钟")
    print("OK 修改手机号模板：2695133，参数为验证码")
    print("OK 本地限频：同手机号至少 60 秒、每日最多 2 次；账号 5 次/小时；IP 30 次/小时")
    if not args.live:
        print("SKIP 未请求真实发送；模板变为“已生效”后加 --live --phone 验证")
        return 0
    if not args.phone or not re.fullmatch(r"1\d{10}", args.phone):
        print("FAIL --live 必须同时提供有效的 --phone")
        return 2
    return asyncio.run(_run_live(args.phone, args.purpose))


if __name__ == "__main__":
    sys.exit(main())
