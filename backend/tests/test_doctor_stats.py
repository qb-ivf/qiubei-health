from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.v1 import doctors


@pytest.mark.asyncio
async def test_my_stats_returns_real_evaluation_metrics(monkeypatch):
    doctor = SimpleNamespace(id=9)
    monkeypatch.setattr(
        doctors,
        "_require_my_doctor",
        AsyncMock(return_value=doctor),
    )
    db = AsyncMock()
    db.scalar.side_effect = [12, 8.666, 5]

    result = await doctors.my_stats(user={"sub": "7"}, db=db)

    assert result == {"consulted": 12, "score": 8.7, "praise": 5}


@pytest.mark.asyncio
async def test_my_stats_has_empty_state_without_evaluations(monkeypatch):
    monkeypatch.setattr(
        doctors,
        "_require_my_doctor",
        AsyncMock(return_value=SimpleNamespace(id=9)),
    )
    db = AsyncMock()
    db.scalar.side_effect = [0, None, 0]

    result = await doctors.my_stats(user={"sub": "7"}, db=db)

    assert result == {"consulted": 0, "score": None, "praise": 0}
