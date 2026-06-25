"""给医生插入号源（号源扣减以 Redis 为准，故同步写入 Redis，否则会被判「约满」）。

在服务器容器内运行：
  docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api \
    python -m scripts.add_slots <doctor_id> [天数=3] [每时段配额=5]

为指定医生从「今天起 N 天」每天生成几个固定时段的号源。可重复运行（同日同时段不重复插）。
"""
import asyncio
import sys
from datetime import date, timedelta

from sqlalchemy import select

from app.core.database import AsyncSessionLocal, engine
from app.core.redis import redis_client
from app.models import Base
from app.models.schedule import Slot
from app.services.doctor_service import slot_key

TIMES = [
    ("09:00", "09:30"), ("09:30", "10:00"), ("10:00", "10:30"),
    ("14:00", "14:30"), ("14:30", "15:00"),
]


async def main() -> None:
    if len(sys.argv) < 2:
        print("用法: python -m scripts.add_slots <doctor_id> [天数=3] [每时段配额=5]")
        return
    doctor_id = int(sys.argv[1])
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    quota = int(sys.argv[3]) if len(sys.argv) > 3 else 5

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    today = date.today()
    created = 0
    async with AsyncSessionLocal() as db:
        for offset in range(days):
            day = (today + timedelta(days=offset)).isoformat()
            for st, et in TIMES:
                exists = await db.scalar(
                    select(Slot.id).where(Slot.doctor_id == doctor_id, Slot.day == day, Slot.start_time == st)
                )
                if exists:
                    continue
                slot = Slot(doctor_id=doctor_id, day=day, start_time=st, end_time=et, quota=quota, remaining=quota)
                db.add(slot)
                await db.flush()
                await redis_client.set(slot_key(slot.id), quota)  # 号源锁
                created += 1
        await db.commit()

    print(f"OK: 医生 #{doctor_id} 新增 {created} 个号源（{days} 天 × {len(TIMES)} 时段，每个 {quota} 号）")
    await engine.dispose()
    try:
        await redis_client.aclose()
    except Exception:  # noqa: BLE001
        pass


if __name__ == "__main__":
    asyncio.run(main())
