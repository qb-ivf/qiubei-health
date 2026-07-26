"""运营后台登录防暴力尝试。

按“用户名 + 客户端 IP”和客户端 IP 两级限流；Redis 键只保存摘要，不暴露用户名。
"""
import hashlib
import ipaddress
import logging

from fastapi import Request

from ..core.redis import redis_client

logger = logging.getLogger("login-security")

WINDOW_SECONDS = 15 * 60
PAIR_FAILURE_LIMIT = 5
IP_FAILURE_LIMIT = 30
_KEY_PREFIX = "security:admin-login"


class LoginRateLimited(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = max(int(retry_after), 1)
        super().__init__("登录尝试过多")


def client_ip(request: Request) -> str:
    """API 仅绑定环回地址，公网请求由可信 Nginx 写入 X-Real-IP。"""
    candidate = (request.headers.get("x-real-ip") or "").strip()
    try:
        if candidate:
            return str(ipaddress.ip_address(candidate))
    except ValueError:
        pass
    return request.client.host if request.client else "unknown"


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def attempt_keys(username: str, ip: str) -> tuple[str, str]:
    normalized_username = (username or "").strip().casefold()
    return (
        f"{_KEY_PREFIX}:pair:{_digest(f'{normalized_username}|{ip}')}",
        f"{_KEY_PREFIX}:ip:{_digest(ip)}",
    )


async def _retry_after(keys: tuple[str, ...]) -> int:
    ttls = [int(await redis_client.ttl(key)) for key in keys]
    positive = [ttl for ttl in ttls if ttl > 0]
    return max(positive, default=WINDOW_SECONDS)


async def ensure_login_allowed(username: str, ip: str) -> None:
    keys = attempt_keys(username, ip)
    try:
        values = await redis_client.mget(*keys)
        pair_count = int(values[0] or 0)
        ip_count = int(values[1] or 0)
        blocked = []
        if pair_count >= PAIR_FAILURE_LIMIT:
            blocked.append(keys[0])
        if ip_count >= IP_FAILURE_LIMIT:
            blocked.append(keys[1])
        if blocked:
            raise LoginRateLimited(await _retry_after(tuple(blocked)))
    except LoginRateLimited:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("登录限流预检异常，暂不阻断本次鉴权: %s", type(exc).__name__)


async def record_login_failure(username: str, ip: str) -> int | None:
    """记录失败；达到阈值时返回 Retry-After 秒数。"""
    keys = attempt_keys(username, ip)
    try:
        counts = []
        for key in keys:
            count = int(await redis_client.incr(key))
            counts.append(count)
            if count == 1:
                await redis_client.expire(key, WINDOW_SECONDS)
        blocked = []
        if counts[0] >= PAIR_FAILURE_LIMIT:
            blocked.append(keys[0])
        if counts[1] >= IP_FAILURE_LIMIT:
            blocked.append(keys[1])
        return await _retry_after(tuple(blocked)) if blocked else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("记录登录失败次数异常: %s", type(exc).__name__)
        return None


async def clear_login_failures(username: str, ip: str) -> None:
    try:
        await redis_client.delete(*attempt_keys(username, ip))
    except Exception as exc:  # noqa: BLE001
        logger.warning("清理登录失败次数异常: %s", type(exc).__name__)
