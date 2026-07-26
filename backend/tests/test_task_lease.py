import pytest

from app.services import task_lease


class _Redis:
    def __init__(self, *, acquired=True):
        self.acquired = acquired
        self.released = []

    async def set(self, key, token, **kwargs):
        assert kwargs == {"nx": True, "ex": 30}
        return self.acquired

    async def eval(self, script, key_count, key, token):
        self.released.append((script, key_count, key, token))
        return 1


@pytest.mark.asyncio
async def test_distributed_lease_releases_only_acquired_lock(monkeypatch):
    fake = _Redis(acquired=True)
    monkeypatch.setattr(task_lease, "redis_client", fake)

    async with task_lease.distributed_lease("worker", 30) as acquired:
        assert acquired is True

    assert len(fake.released) == 1
    assert fake.released[0][2] == "task:lease:worker"


@pytest.mark.asyncio
async def test_distributed_lease_does_not_release_foreign_lock(monkeypatch):
    fake = _Redis(acquired=False)
    monkeypatch.setattr(task_lease, "redis_client", fake)

    async with task_lease.distributed_lease("worker", 30) as acquired:
        assert acquired is False

    assert fake.released == []
