"""从受控 Excel 工作簿校验并幂等导入医生、审方药师。

默认 dry-run，不写数据库：
    python -m scripts.import_personnel /secure/人员批量导入-YYYYMMDD.xlsx

正式导入：
    python -m scripts.import_personnel /secure/人员批量导入-YYYYMMDD.xlsx \
      --apply --confirm-organ-id <统一社会信用代码> \
      --credentials-out /secure/药师初始密码-YYYYMMDD.csv

医生本人必须先用手机号登录医生端一次。本脚本不会创建或伪造微信 openid。
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import os
from pathlib import Path

from cryptography.fernet import Fernet
from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.models.staff import Staff
from app.models.user import Doctor, User
from app.services.personnel_import_service import (
    apply_database_plan,
    build_database_plan,
    parse_personnel_workbook,
    write_credentials_file,
)


BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent
# 生产容器只把 backend 挂到 /app，宿主仓库根目录并不在容器内；此时 /app 即敏感文件禁入区。
WORKTREE_DIR = BACKEND_DIR if REPO_DIR == Path(REPO_DIR.anchor) else REPO_DIR
DICT_DIR = BACKEND_DIR / "data" / "tj_dicts"


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _runtime_errors(args) -> list[str]:
    errors: list[str] = []
    if not settings.ENCRYPTION_KEY:
        errors.append("ENCRYPTION_KEY 未设置，禁止读取或写入人员身份证")
    else:
        try:
            Fernet(settings.ENCRYPTION_KEY.encode())
        except (TypeError, ValueError):
            errors.append("ENCRYPTION_KEY 不是有效 Fernet 密钥")
    if _inside(args.workbook, WORKTREE_DIR):
        errors.append("含个人信息的工作簿不得放在 Git 工作区内")
    if os.name == "posix" and args.workbook.exists() and args.workbook.stat().st_mode & 0o077:
        errors.append("工作簿权限过宽，读取前必须 chmod 600")
    if args.approve_doctors and not args.apply:
        errors.append("--approve-doctors 只能与 --apply 同时使用")
    if args.apply:
        if settings.DEBUG:
            errors.append("DEBUG 必须为 false 才能正式导入")
        if settings.DOCTOR_AUTO_APPROVE:
            errors.append("DOCTOR_AUTO_APPROVE 必须为 false，避免未核验医生自动通过")
        configured_id = (settings.ORGAN_ID or settings.FXQ_COMPANY_IDNO).strip().upper()
        if not configured_id:
            errors.append("ORGAN_ID/FXQ_COMPANY_IDNO 未配置，无法确认导入目标机构")
        elif (args.confirm_organ_id or "").strip().upper() != configured_id:
            errors.append("--confirm-organ-id 与服务器配置不一致")
    return errors


async def _build_plan(db, data):
    doctor_accounts = list((await db.execute(
        select(Doctor, User)
        .join(User, Doctor.user_id == User.id)
        .where(User.role == "doctor")
        .order_by(Doctor.id)
    )).all())
    staff = list((await db.scalars(select(Staff).order_by(Staff.id))).all())
    return build_database_plan(data, doctor_accounts, staff)


def _credentials_path_error(path: Path | None) -> str | None:
    if path is None:
        return "新增药师时必须指定 --credentials-out 绝对路径"
    if not path.is_absolute():
        return "--credentials-out 必须使用绝对路径"
    if not path.parent.is_dir():
        return "凭据输出目录不存在"
    if path.exists():
        return "凭据输出文件已存在；为防止覆盖必须更换新文件名"
    if os.name == "posix" and path.parent.stat().st_mode & 0o077:
        return "凭据输出目录权限过宽，必须先 chmod 700"
    return None


def _workbook_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


async def _apply(data, args) -> int:
    credentials_written = False
    try:
        async with AsyncSessionLocal() as db:
            # 正式写入前在同一事务会话重新匹配，避免使用 detached ORM 对象或过期 dry-run 结果。
            plan = await _build_plan(db, data)
            if plan.errors:
                for issue in plan.issues:
                    print(issue.render())
                await db.rollback()
                print("正式写入前数据库状态已变化；本次未写入任何数据。")
                return 1
            if plan.new_pharmacists:
                path_error = _credentials_path_error(args.credentials_out)
                if path_error:
                    await db.rollback()
                    print(f"[ERROR] 凭据文件: {path_error}")
                    return 2
            digest = _workbook_digest(args.workbook)
            result = await apply_database_plan(
                db,
                plan,
                approve_doctors=args.approve_doctors,
                source_digest=digest,
            )
            if result.credentials:
                write_credentials_file(args.credentials_out, result.credentials)
                credentials_written = True
            await db.commit()
    except Exception as exc:  # noqa: BLE001
        if credentials_written and args.credentials_out:
            args.credentials_out.unlink(missing_ok=True)
        print(f"[ERROR] 正式导入失败并已回滚（{type(exc).__name__}）；未输出任何人员明细")
        return 2

    print(
        "OK 正式导入完成："
        f"医生更新 {result.doctors_updated}，医生终审 {result.doctors_approved}，"
        f"药师新增 {result.pharmacists_created}，药师更新 {result.pharmacists_updated}"
    )
    if result.credentials:
        print("OK 随机药师初始凭据已写入受控文件（路径及内容未回显）")
    return 0


async def run(args) -> int:
    runtime_errors = _runtime_errors(args)
    if runtime_errors:
        for message in runtime_errors:
            print(f"[ERROR] 运行环境: {message}")
        return 2

    data = parse_personnel_workbook(args.workbook, DICT_DIR)
    for issue in data.issues:
        print(issue.render())
    if data.errors:
        print(f"校验失败：{len(data.errors)} 个错误；未连接数据库，未写入任何数据。")
        return 1
    if not data.doctors and not data.pharmacists:
        print("[ERROR] 工作簿没有可导入的医生或药师行")
        return 1

    try:
        async with AsyncSessionLocal() as db:
            plan = await _build_plan(db, data)
            await db.rollback()
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] 数据库只读匹配失败（{type(exc).__name__}）；未输出任何人员明细")
        return 2
    for issue in plan.issues:
        print(issue.render())
    if plan.errors:
        print(f"匹配失败：{len(plan.errors)} 个错误；未写入任何数据。")
        return 1

    print(
        "OK 预检通过："
        f"医生 {len(plan.doctors)}，药师 {len(plan.pharmacists)}"
        f"（新增 {plan.new_pharmacists}，更新 {len(plan.pharmacists) - plan.new_pharmacists}），"
        f"护士留档 {data.nurse_rows}"
    )
    if not args.apply:
        print("DRY-RUN 完成：数据库未写入、未生成密码。确认无误后再使用 --apply。")
        return 0
    return await _apply(data, args)


def main() -> int:
    parser = argparse.ArgumentParser(description="医生/药师人员工作簿安全批量导入")
    parser.add_argument("workbook", type=Path, help="受控目录中的 .xlsx 工作簿")
    parser.add_argument("--apply", action="store_true", help="正式写库；默认只读校验")
    parser.add_argument("--confirm-organ-id", help="正式导入时再次输入统一社会信用代码")
    parser.add_argument("--credentials-out", type=Path, help="新增药师随机初始密码的绝对输出路径")
    parser.add_argument(
        "--approve-doctors",
        action="store_true",
        help="按表内医务审核结论同步医生终审状态；未设置时只补录资料",
    )
    args = parser.parse_args()
    try:
        return asyncio.run(run(args))
    finally:
        asyncio.run(engine.dispose())


if __name__ == "__main__":
    raise SystemExit(main())
