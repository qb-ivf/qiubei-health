from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.v1 import auth
from app.services import login_security, staff_service


class _FakeRedis:
    def __init__(self):
        self.values = {}
        self.ttls = {}

    async def mget(self, *keys):
        return [self.values.get(key) for key in keys]

    async def incr(self, key):
        value = int(self.values.get(key, 0)) + 1
        self.values[key] = value
        return value

    async def expire(self, key, seconds):
        self.ttls[key] = seconds
        return True

    async def ttl(self, key):
        return self.ttls.get(key, -1)

    async def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)
            self.ttls.pop(key, None)
        return len(keys)


def _request(real_ip: str = "203.0.113.8") -> Request:
    return Request({
        "type": "http",
        "method": "POST",
        "path": "/api/v1/auth/admin/login",
        "headers": [(b"x-real-ip", real_ip.encode())],
        "client": ("127.0.0.1", 12345),
    })


@pytest.mark.parametrize("password", [
    "Short1!",
    "alllowercasebutlong",
    "1234567890123456",
])
def test_staff_password_policy_rejects_weak_passwords(password):
    with pytest.raises(staff_service.StaffError):
        staff_service.validate_password_strength(password)


def test_staff_password_policy_accepts_strong_and_rejects_bcrypt_overflow():
    staff_service.validate_password_strength("Correct-Horse-42")

    with pytest.raises(staff_service.StaffError, match="72 字节"):
        staff_service.validate_password_strength("密" * 25)


@pytest.mark.asyncio
async def test_five_failed_logins_are_limited_and_success_can_clear(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(login_security, "redis_client", fake)

    for _ in range(login_security.PAIR_FAILURE_LIMIT - 1):
        assert await login_security.record_login_failure("Admin", "203.0.113.8") is None
    retry_after = await login_security.record_login_failure("Admin", "203.0.113.8")

    assert retry_after == login_security.WINDOW_SECONDS
    with pytest.raises(login_security.LoginRateLimited):
        await login_security.ensure_login_allowed("admin", "203.0.113.8")

    await login_security.clear_login_failures("admin", "203.0.113.8")
    await login_security.ensure_login_allowed("admin", "203.0.113.8")


@pytest.mark.asyncio
async def test_single_ip_is_limited_across_many_usernames(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr(login_security, "redis_client", fake)

    retry_after = None
    for index in range(login_security.IP_FAILURE_LIMIT):
        retry_after = await login_security.record_login_failure(f"user-{index}", "203.0.113.9")

    assert retry_after == login_security.WINDOW_SECONDS
    with pytest.raises(login_security.LoginRateLimited):
        await login_security.ensure_login_allowed("another-user", "203.0.113.9")


def test_login_limit_keys_hide_username_and_client_ip_uses_nginx_header():
    keys = login_security.attempt_keys("SensitiveAdmin", "203.0.113.8")

    assert all("SensitiveAdmin" not in key for key in keys)
    assert login_security.client_ip(_request()) == "203.0.113.8"
    assert login_security.client_ip(_request("not-an-ip")) == "127.0.0.1"


@pytest.mark.asyncio
async def test_admin_login_returns_429_with_retry_after(monkeypatch):
    async def blocked(_username, _ip):
        raise login_security.LoginRateLimited(321)

    monkeypatch.setattr(login_security, "ensure_login_allowed", blocked)

    with pytest.raises(HTTPException) as exc:
        await auth.admin_login(
            SimpleNamespace(username="admin", password="wrong"),
            _request(),
            db=None,
        )

    assert exc.value.status_code == 429
    assert exc.value.headers["Retry-After"] == "321"
