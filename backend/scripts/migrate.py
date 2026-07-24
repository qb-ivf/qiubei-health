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
    # —— S3 上报调度层 ——
    ("gov_reports", "method", "VARCHAR(64) NULL"),
    ("gov_reports", "payload", "JSON NULL"),
    ("gov_reports", "batch_date", "DATE NULL"),
    ("gov_reports", "next_retry_at", "DATETIME NULL"),
    ("gov_reports", "msg_code", "INT NULL"),
    ("gov_reports", "resp_msg", "VARCHAR(500) NULL"),
    ("prescriptions", "recipe_unique_id", "VARCHAR(64) NULL"),
    ("prescriptions", "checked_at", "DATETIME NULL"),
    ("prescriptions", "audit_staff_id", "BIGINT NULL"),
    ("doctors", "id_card_enc", "VARCHAR(255) NULL"),
    ("doctors", "subject_code", "VARCHAR(10) NULL"),
    ("doctors", "subject_name", "VARCHAR(30) NULL"),
    ("doctors", "dept_code", "VARCHAR(10) NULL"),
    ("staff", "id_card_enc", "VARCHAR(255) NULL"),
    ("patients", "cert_type", "VARCHAR(10) NOT NULL DEFAULT '1'"),
    ("patients", "guardian_name", "VARCHAR(50) NULL"),
    ("patients", "guardian_cert_enc", "VARCHAR(255) NULL"),
    ("patients", "guardian_mobile", "VARCHAR(20) NULL"),
    ("drugs", "drug_class", "VARCHAR(50) NULL"),
    ("drugs", "countrydrcode", "VARCHAR(50) NULL"),
    ("drugs", "packing", "VARCHAR(30) NULL"),
    ("drugs", "manufacturer", "VARCHAR(60) NULL"),
    ("drugs", "use_flag", "VARCHAR(1) NOT NULL DEFAULT '1'"),
    # —— 放心签双录与处方签章追踪 ——
    ("prescriptions", "doctor_ca_order_no", "VARCHAR(64) NULL"),
    ("prescriptions", "pharmacist_ca_order_no", "VARCHAR(64) NULL"),
]

TABLE_DDLS = [
    """
    CREATE TABLE IF NOT EXISTS ca_enrollments (
        id BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        subject_type VARCHAR(16) NOT NULL,
        subject_id BIGINT NOT NULL,
        provider_user_id VARCHAR(64) NOT NULL,
        order_no VARCHAR(64) NOT NULL UNIQUE,
        verify_id VARCHAR(64) NULL,
        trade_no VARCHAR(64) NULL,
        status VARCHAR(16) NOT NULL DEFAULT 'pending',
        agreement_url_enc TEXT NULL,
        provider_code VARCHAR(16) NULL,
        face_code VARCHAR(16) NULL,
        provider_msg VARCHAR(255) NULL,
        live_rate VARCHAR(16) NULL,
        similarity VARCHAR(16) NULL,
        occurred_at DATETIME NULL,
        last_checked_at DATETIME NULL,
        completed_at DATETIME NULL,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX ix_ca_enrollments_subject_type (subject_type),
        INDEX ix_ca_enrollments_subject_id (subject_id),
        INDEX ix_ca_enrollments_status (status)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
]


async def main() -> None:
    async with engine.begin() as conn:
        for ddl in TABLE_DDLS:
            await conn.execute(text(ddl))
            print("ensured ca_enrollments")
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
