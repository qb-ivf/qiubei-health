"""Redis 客户端（信令在线状态、号源锁、排队队列、键空间超时取消）。"""
import redis.asyncio as aioredis

from .config import settings

redis_client = aioredis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)


async def get_redis() -> aioredis.Redis:
    return redis_client
