"""创建缺失的数据库表（无 Alembic 时的建表工具，pending #21）。

生产 DEBUG=false 不会自动建表；新增模型后在服务器运行一次：
  docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api python -m scripts.init_db

只创建尚不存在的表，不影响已有表/数据。
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
