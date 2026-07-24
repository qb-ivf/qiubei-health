"""天津监管正式切换只读预检。

默认按正式环境标准检查配置、基础资料和上报队列，不写数据库、不请求监管平台：
    python scripts/tj_preflight.py

退出码 0 表示没有阻断项；1 表示存在必须先修复的 FAIL。
"""
import argparse
import asyncio
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet
from sqlalchemy import func, select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.core.crypto import decrypt  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402
from app.models.drug import Drug  # noqa: E402
from app.models.gov_report import GovReport  # noqa: E402
from app.models.staff import Staff  # noqa: E402
from app.models.user import Doctor  # noqa: E402
from app.services.tj_config import (  # noqa: E402
    gateway_config_errors,
    is_production_gateway,
    is_test_gateway,
)


@dataclass(frozen=True)
class Check:
    level: str
    area: str
    message: str


def _ids(items) -> str:
    values = [str(x.id) for x in items]
    return ",".join(values[:20]) + ("…" if len(values) > 20 else "")


def _id_card_decrypts(value: str | None) -> bool:
    if not value:
        return False
    try:
        plain = decrypt(value) or ""
    except Exception:  # noqa: BLE001
        return False
    return bool(re.fullmatch(r"\d{17}[\dXx]", plain))


def config_checks(*, require_production: bool) -> list[Check]:
    checks: list[Check] = []
    errors = gateway_config_errors(settings, require_production=require_production)
    if errors:
        checks.extend(Check("FAIL", "配置", e) for e in errors)
    else:
        env_name = "正式" if is_production_gateway(settings.TJ_GATEWAY_URL) else "测试"
        checks.append(Check("PASS", "配置", f"{env_name}网关地址与机构凭据格式有效（凭据已脱敏）"))

    if settings.DEBUG and require_production:
        checks.append(Check("FAIL", "配置", "DEBUG 必须设为 false 后才能正式切换"))
    else:
        checks.append(Check("PASS", "配置", f"DEBUG={str(settings.DEBUG).lower()}"))

    if not settings.ENCRYPTION_KEY:
        checks.append(Check("FAIL", "配置", "ENCRYPTION_KEY 未设置；不得用开发回退密钥保存医患身份证"))
    else:
        try:
            Fernet(settings.ENCRYPTION_KEY.encode())
            checks.append(Check("PASS", "配置", "ENCRYPTION_KEY 格式有效"))
        except (TypeError, ValueError):
            checks.append(Check("FAIL", "配置", "ENCRYPTION_KEY 不是有效 Fernet 密钥"))

    if settings.JWT_SECRET == "CHANGE_ME_IN_PROD":
        checks.append(Check("FAIL", "配置", "JWT_SECRET 仍为开发默认值"))

    if settings.TJ_REPORT_ENABLED:
        checks.append(Check("PASS", "开关", "TJ_REPORT_ENABLED=true（正式请求将真实发送）"))
    else:
        checks.append(Check("WARN", "开关", "TJ_REPORT_ENABLED=false；预检阶段正确，正式启动前再开启"))
    return checks


async def database_checks() -> list[Check]:
    checks: list[Check] = []
    try:
        async with AsyncSessionLocal() as db:
            doctors = list((await db.scalars(
                select(Doctor).where(Doctor.audit_status == "approved").order_by(Doctor.id)
            )).all())
            if not doctors:
                checks.append(Check("FAIL", "医生", "没有已终审通过的医生"))
            else:
                missing = [d for d in doctors if not all(
                    (d.name, d.dept, d.subject_code, d.subject_name, d.dept_code, d.id_card_enc)
                )]
                bad_cert = [d for d in doctors if d.id_card_enc and not _id_card_decrypts(d.id_card_enc)]
                out_of_scope = [d for d in doctors if d.subject_code and not d.subject_code.startswith(("03", "05", "50"))]
                if missing:
                    checks.append(Check("FAIL", "医生", f"{len(missing)} 名已通过医生监管字段不全（ID: {_ids(missing)}）"))
                if bad_cert:
                    checks.append(Check("FAIL", "医生", f"{len(bad_cert)} 名医生身份证无法用当前密钥解密/格式错误（ID: {_ids(bad_cert)}）"))
                if out_of_scope:
                    checks.append(Check("FAIL", "医生", f"{len(out_of_scope)} 名医生科目超出 03/05/50 许可范围（ID: {_ids(out_of_scope)}）"))
                if not (missing or bad_cert or out_of_scope):
                    checks.append(Check("PASS", "医生", f"{len(doctors)} 名已通过医生监管资料完整"))

            pharmacists = list((await db.scalars(
                select(Staff).where(Staff.role == "pharmacist", Staff.active.is_(True)).order_by(Staff.id)
            )).all())
            if not pharmacists:
                checks.append(Check("FAIL", "药师", "没有启用的审方药师账号"))
            else:
                missing = [s for s in pharmacists if not s.name or not s.id_card_enc]
                bad_cert = [s for s in pharmacists if s.id_card_enc and not _id_card_decrypts(s.id_card_enc)]
                if missing:
                    checks.append(Check("FAIL", "药师", f"{len(missing)} 名药师缺真实姓名或身份证（ID: {_ids(missing)}）"))
                if bad_cert:
                    checks.append(Check("FAIL", "药师", f"{len(bad_cert)} 名药师身份证无法用当前密钥解密/格式错误（ID: {_ids(bad_cert)}）"))
                if not (missing or bad_cert):
                    checks.append(Check("PASS", "药师", f"{len(pharmacists)} 名启用药师监管资料完整"))

            drugs = list((await db.scalars(
                select(Drug).where(Drug.use_flag == "1").order_by(Drug.id)
            )).all())
            if not drugs:
                checks.append(Check("FAIL", "药品", "没有可备案的在用药品"))
            else:
                missing = [d for d in drugs if not (
                    d.name and d.drug_class and (d.packing or d.spec) and d.manufacturer and d.price_fen > 0
                )]
                if missing:
                    checks.append(Check("FAIL", "药品", f"{len(missing)} 个在用药品缺分类/包装/厂家/价格（ID: {_ids(missing)}）"))
                else:
                    checks.append(Check("PASS", "药品", f"{len(drugs)} 个在用药品达到目录备案条件"))

            failed = await db.scalar(select(func.count()).select_from(GovReport).where(
                GovReport.status.in_(("failed", "dead"))
            )) or 0
            pending = await db.scalar(select(func.count()).select_from(GovReport).where(
                GovReport.status == "pending"
            )) or 0
            simulated = await db.scalar(select(func.count()).select_from(GovReport).where(
                GovReport.status == "success", GovReport.resp_msg.like("本地模拟成功%")
            )) or 0
            malformed = await db.scalar(select(func.count()).select_from(GovReport).where(
                GovReport.status.in_(("pending", "failed")),
                (GovReport.method.is_(None)) | (GovReport.payload.is_(None)),
            )) or 0
            if failed:
                checks.append(Check("FAIL", "队列", f"存在 {failed} 条失败/死信，切换前需处理"))
            if malformed:
                checks.append(Check("FAIL", "队列", f"存在 {malformed} 条待发任务缺 method/payload"))
            if not (failed or malformed):
                checks.append(Check("PASS", "队列", "没有失败、死信或畸形待发任务"))
            checks.append(Check("PASS", "队列", f"当前 pending {pending} 条（开启后将按药品目录优先发送）"))
            if simulated:
                checks.append(Check(
                    "WARN", "队列",
                    f"历史有 {simulated} 条“本地模拟成功”；请确认均早于自建系统正式上报起始日，否则需按日期补采",
                ))
    except Exception as exc:  # noqa: BLE001
        checks.append(Check("FAIL", "数据库", f"无法完成只读检查：{type(exc).__name__}: {exc}"))
    return checks


async def run(require_production: bool) -> list[Check]:
    return config_checks(require_production=require_production) + await database_checks()


def main() -> int:
    parser = argparse.ArgumentParser(description="天津监管正式切换只读预检")
    parser.add_argument("--test", action="store_true", help="按测试网关检查（默认要求正式网关）")
    args = parser.parse_args()
    checks = asyncio.run(run(require_production=not args.test))
    icons = {"PASS": "[PASS]", "WARN": "[WARN]", "FAIL": "[FAIL]"}
    for item in checks:
        print(f"{icons[item.level]} {item.area}: {item.message}")
    failures = sum(item.level == "FAIL" for item in checks)
    warnings = sum(item.level == "WARN" for item in checks)
    print(f"\n预检完成：{failures} 个阻断项，{warnings} 个提醒。全程未写库、未请求监管平台。")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
