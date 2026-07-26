"""Redis 分布式任务租约，防止多 API 实例重复执行后台扫描。"""
import uuid
from contextlib import asynccontextmanager

from ..core.redis import redis_client

_RELEASE_SCRIPT = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""


@asynccontextmanager
async def distributed_lease(name: str, ttl_seconds: int):
    """尝试取得带所有权令牌的租约；Redis 异常时安全地返回未取得。"""
    key = f"task:lease:{name}"
    token = uuid.uuid4().hex
    try:
        acquired = bool(await redis_client.set(key, token, nx=True, ex=ttl_seconds))
    except Exception:  # noqa: BLE001
        acquired = False
    try:
        yield acquired
    finally:
        if acquired:
            try:
                await redis_client.eval(_RELEASE_SCRIPT, 1, key, token)
            except Exception:  # noqa: BLE001
                pass
