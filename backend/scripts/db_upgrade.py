"""安全接管既有数据库并升级到最新 Alembic 版本。

用法：
  python -m scripts.db_upgrade

- 全新数据库：执行全部 Alembic 迁移；
- 已有但尚无 alembic_version 的数据库：先用旧版幂等工具补齐当前结构，再 stamp 基线；
- 已纳入 Alembic 的数据库：正常 upgrade head。

脚本不会删除表、列或业务数据，也不会输出数据库凭据。
"""
import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.core.database import engine
from app.models import Base

BACKEND_DIR = Path(__file__).resolve().parents[1]
VERSION_TABLE = "alembic_version"


def classify_schema(table_names: set[str]) -> str:
    """返回 versioned / legacy / empty，供主流程和单元测试共用。"""
    if VERSION_TABLE in table_names:
        return "versioned"
    if table_names.intersection(Base.metadata.tables):
        return "legacy"
    return "empty"


def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return cfg


async def _table_names() -> set[str]:
    try:
        async with engine.connect() as conn:
            return await conn.run_sync(lambda sync_conn: set(inspect(sync_conn).get_table_names()))
    finally:
        await engine.dispose()


def main() -> int:
    state = classify_schema(asyncio.run(_table_names()))
    cfg = alembic_config()

    if state == "legacy":
        # 仅第一次接管既有数据库时运行；两个旧工具均为只增不删且可重复执行。
        from scripts.init_db import main as ensure_tables
        from scripts.migrate import main as ensure_columns

        print("INFO: 检测到既有未版本化数据库，先执行幂等结构补齐")
        asyncio.run(ensure_tables())
        asyncio.run(ensure_columns())
        command.stamp(cfg, "head")
        print("OK: 既有数据库已安全接管并标记为 Alembic head")
        return 0

    command.upgrade(cfg, "head")
    if state == "empty":
        print("OK: 全新数据库已升级到 Alembic head")
    else:
        print("OK: 数据库已升级到 Alembic head")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
