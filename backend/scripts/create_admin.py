"""创建 / 重置运营后台账号（admin / pharmacist / finance）。

在服务器上运行（容器内）：
  docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api \
    python -m scripts.create_admin <username> <password> [role]

role 取值：admin（默认，全权）/ pharmacist（药师审方）/ finance（财务）。
首次运行会自动建 staff 表（仅创建缺失表，不影响现有数据）。
"""
import asyncio
import sys

from app.constants import Role
from app.core.database import AsyncSessionLocal, engine
from app.models import Base
from app.services import staff_service

VALID_ROLES = {Role.ADMIN, Role.PHARMACIST, Role.FINANCE}


async def main() -> None:
    if len(sys.argv) < 3:
        print("用法: python -m scripts.create_admin <username> <password> [role]")
        print("role: admin(默认) / pharmacist / finance")
        return
    username, password = sys.argv[1], sys.argv[2]
    role = sys.argv[3] if len(sys.argv) > 3 else Role.ADMIN
    if role not in VALID_ROLES:
        print(f"非法角色 {role}，可选：{', '.join(sorted(VALID_ROLES))}")
        return

    # 仅创建缺失的表（staff）；现有表不受影响
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        staff = await staff_service.upsert(db, username, password, role)
        await db.commit()
        print(f"OK: staff #{staff.id} username={username} role={role}")

    await engine.dispose()  # 干净释放连接池，避免退出时 Event loop 报错


if __name__ == "__main__":
    asyncio.run(main())
