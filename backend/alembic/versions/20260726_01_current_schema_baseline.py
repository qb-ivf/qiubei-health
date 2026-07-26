"""建立当前完整数据库结构基线。

Revision ID: 20260726_01
Revises:
Create Date: 2026-07-26

既有生产库不会执行本迁移的建表逻辑，而是由 scripts.db_upgrade 先运行旧版幂等补齐工具，
确认当前结构后 stamp 到此版本。全新数据库才会从 ORM metadata 创建完整结构。
"""
from alembic import op

from app.models import Base

revision = "20260726_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind(), checkfirst=False)


def downgrade() -> None:
    raise RuntimeError("禁止回退数据库基线：该操作会删除业务表，请使用备份恢复方案")
