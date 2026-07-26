from contextlib import asynccontextmanager
from datetime import date
from unittest.mock import AsyncMock

import pytest

import main


@pytest.mark.asyncio
async def test_daily_collect_skips_completed_batch(monkeypatch):
    redis = AsyncMock()
    redis.exists.return_value = 1
    monkeypatch.setattr(main, "redis_client", redis)

    result = await main._collect_tj_day_once(date(2026, 7, 25))

    assert result == "already_completed"


@pytest.mark.asyncio
async def test_daily_collect_marks_batch_only_after_success(monkeypatch):
    redis = AsyncMock()
    redis.exists.side_effect = [0, 0]
    monkeypatch.setattr(main, "redis_client", redis)

    @asynccontextmanager
    async def acquired_lease(*_args, **_kwargs):
        yield True

    db = object()

    class Session:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *_args):
            return False

    collect = AsyncMock(return_value={"recipe": 2})
    monkeypatch.setattr(main, "distributed_lease", acquired_lease)
    monkeypatch.setattr(main, "AsyncSessionLocal", Session)
    monkeypatch.setattr(main.tj_collector, "collect_daily", collect)

    day = date(2026, 7, 25)
    result = await main._collect_tj_day_once(day)

    assert result == "completed"
    collect.assert_awaited_once_with(db, day)
    redis.set.assert_awaited_once_with(
        "task:done:tj-daily-collect:2026-07-25",
        "1",
        ex=3 * 24 * 60 * 60,
    )


@pytest.mark.asyncio
async def test_daily_collect_does_not_mark_failed_batch(monkeypatch):
    redis = AsyncMock()
    redis.exists.side_effect = [0, 0]
    monkeypatch.setattr(main, "redis_client", redis)

    @asynccontextmanager
    async def acquired_lease(*_args, **_kwargs):
        yield True

    class Session:
        async def __aenter__(self):
            return object()

        async def __aexit__(self, *_args):
            return False

    monkeypatch.setattr(main, "distributed_lease", acquired_lease)
    monkeypatch.setattr(main, "AsyncSessionLocal", Session)
    monkeypatch.setattr(
        main.tj_collector,
        "collect_daily",
        AsyncMock(side_effect=RuntimeError("gateway unavailable")),
    )

    with pytest.raises(RuntimeError, match="gateway unavailable"):
        await main._collect_tj_day_once(date(2026, 7, 25))
    redis.set.assert_not_awaited()
