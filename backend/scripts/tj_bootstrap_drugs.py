"""正式环境首次药品目录入队工具（默认预览，不直接请求监管平台）。

预览：python scripts/tj_bootstrap_drugs.py
执行：python scripts/tj_bootstrap_drugs.py --apply --confirm-unit <TJ_UNIT_ID>

执行只会把全部在用药品刷新为 pending；随后由正式 worker 按目录优先发送。
"""
import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402
from app.models.drug import Drug  # noqa: E402
from app.services import compliance_service, tj_mappers  # noqa: E402
from app.services.tj_config import gateway_config_errors  # noqa: E402


async def run(*, apply: bool, confirm_unit: str | None) -> int:
    errors = gateway_config_errors(settings, require_production=True)
    if errors:
        for error in errors:
            print(f"[FAIL] {error}")
        return 1
    if settings.DEBUG:
        print("[FAIL] DEBUG=true；拒绝按正式环境执行目录初始化")
        return 1
    if settings.TJ_REPORT_ENABLED:
        print("[FAIL] 请先保持 TJ_REPORT_ENABLED=false，完成目录入队后再统一开启")
        return 1
    if apply and confirm_unit != settings.TJ_UNIT_ID:
        print("[FAIL] --confirm-unit 与当前 TJ_UNIT_ID 不一致")
        return 1

    async with AsyncSessionLocal() as db:
        drugs = list((await db.scalars(
            select(Drug).where(Drug.use_flag == "1").order_by(Drug.id)
        )).all())
        incomplete = [d for d in drugs if not (
            d.name and d.drug_class and (d.packing or d.spec) and d.manufacturer and d.price_fen > 0
        )]
        if not drugs:
            print("[FAIL] 没有可备案的在用药品")
            return 1
        if incomplete:
            ids = ",".join(str(d.id) for d in incomplete[:20])
            print(f"[FAIL] {len(incomplete)} 个药品备案字段不全（ID: {ids}）")
            return 1
        print(f"[PASS] 将刷新 {len(drugs)} 个在用药品的正式目录任务")
        if not apply:
            print("预览完成：未写数据库。确认后添加 --apply --confirm-unit <TJ_UNIT_ID>。")
            return 0
        for drug in drugs:
            await compliance_service.enqueue(
                db, "drug", drug.id, "uploadDrugCatalogue",
                [tj_mappers.build_drug(drug)], refresh=True,
            )
        await db.commit()
        print(f"[PASS] 已入队 {len(drugs)} 条；仍未请求监管平台。现在可开启 TJ_REPORT_ENABLED 并重启 API。")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="天津监管正式药品目录初始化")
    parser.add_argument("--apply", action="store_true", help="执行入队（默认仅预览）")
    parser.add_argument("--confirm-unit", help="执行时必须再次输入当前 TJ_UNIT_ID")
    args = parser.parse_args()
    return asyncio.run(run(apply=args.apply, confirm_unit=args.confirm_unit))


if __name__ == "__main__":
    raise SystemExit(main())
