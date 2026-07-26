"""创建缺失数据库表的旧版兼容工具。

新部署统一运行 ``python -m scripts.db_upgrade``。本文件只供首次接管尚未纳入 Alembic
的既有数据库使用；只创建缺失表，不影响已有表或数据。
"""
import asyncio

from app.core.database import engine
from app.models import Base


async def main() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("OK: 已确保所有表存在")


if __name__ == "__main__":
    asyncio.run(main())
