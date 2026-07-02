"""轻量迁移：为已有表补列（无 Alembic 的过渡方案，pending #21）。重复执行安全。

用法（服务器）：
  docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api python -m scripts.migrate
"""
import asyncio

from sqlalchemy import text

from app.core.database import engine

# (表, 列, 列定义)
COLUMNS = [
    ("orders", "consult_type", "VARCHAR(8) NOT NULL DEFAULT 'video'"),
    ("patients", "phone_enc", "VARCHAR(255) NULL"),
    # —— 天津监管上报字段（docs/tianjin_supervision_plan.md S2） ——
    ("orders", "paid_at", "DATETIME NULL"),
    ("orders", "accepted_at", "DATETIME NULL"),
    ("orders", "finished_at", "DATETIME NULL"),
    ("orders", "cancel_reason", "VARCHAR(64) NULL"),
    ("orders", "wx_transaction_id", "VARCHAR(64) NULL"),
    ("orders", "wx_drug_transaction_id", "VARCHAR(64) NULL"),
    ("orders", "referral_flag", "TINYINT(1) NULL"),
    ("orders", "original_diagnosis", "VARCHAR(255) NULL"),
    ("orders", "first_diagnosis_file_ids", "VARCHAR(300) NULL"),
    ("prescriptions", "icd_code", "VARCHAR(64) NULL"),
    ("prescriptions", "icd_name", "VARCHAR(255) NULL"),
]


async def main() -> None:
    async with engine.begin() as conn:
        for table, col, ddl in COLUMNS:
            exists = await conn.scalar(
                text(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema=DATABASE() AND table_name=:t AND column_name=:c"
                ),
                {"t": table, "c": col},
            )
            if exists:
                print(f"skip {table}.{col}（已存在）")
                continue
            await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {ddl}"))
            print(f"added {table}.{col}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
