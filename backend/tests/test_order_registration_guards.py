from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.schedule import Slot
from app.models.user import Doctor, Patient
from app.services import order_service


class _Scalars:
    def __init__(self, value):
        self.value = value

    def first(self):
        return self.value


class _Result:
    def __init__(self, value):
        self.value = value

    def scalars(self):
        return _Scalars(self.value)


class _Db:
    def __init__(self, *, doctor=None, patient=None, slot=None, consent=None, flush_error=None):
        self.values = {Doctor: doctor, Patient: patient, Slot: slot}
        self.consent = consent
        self.flush_error = flush_error
        self.added = []

    async def get(self, model, _value):
        return self.values.get(model)

    async def execute(self, _query):
        return _Result(self.consent)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        if self.flush_error:
            raise self.flush_error
        return None


def _valid_db(**overrides):
    values = {
        "doctor": SimpleNamespace(id=3, audit_status="approved", register_fee_fen=5000),
        "patient": SimpleNamespace(id=4, user_id=7, verified=True),
        "slot": SimpleNamespace(id=5, doctor_id=3),
        "consent": object(),
    }
    values.update(overrides)
    return _Db(**values)


@pytest.mark.asyncio
async def test_registration_rejects_other_accounts_patient(monkeypatch):
    redis = AsyncMock()
    monkeypatch.setattr(order_service, "redis_client", redis)
    db = _valid_db(patient=SimpleNamespace(id=4, user_id=99, verified=True))

    with pytest.raises(order_service.StateError, match="不属于当前账号"):
        await order_service.create_register_order(db, 7, 3, 5, 4, "text")
    redis.decr.assert_not_awaited()


@pytest.mark.asyncio
async def test_registration_requires_server_side_consent(monkeypatch):
    redis = AsyncMock()
    monkeypatch.setattr(order_service, "redis_client", redis)
    db = _valid_db(consent=None)

    with pytest.raises(order_service.StateError, match="知情同意"):
        await order_service.create_register_order(db, 7, 3, 5, 4, "text")
    redis.decr.assert_not_awaited()


@pytest.mark.asyncio
async def test_video_registration_requires_positive_referral_declaration(monkeypatch):
    redis = AsyncMock()
    monkeypatch.setattr(order_service, "redis_client", redis)

    with pytest.raises(order_service.StateError, match="仅提供复诊"):
        await order_service.create_register_order(_valid_db(), 7, 3, 5, 4, "video", referral_flag=None)
    redis.decr.assert_not_awaited()


@pytest.mark.asyncio
async def test_valid_registration_consumes_selected_doctors_slot(monkeypatch):
    redis = AsyncMock()
    redis.decr.return_value = 2
    monkeypatch.setattr(order_service, "redis_client", redis)
    db = _valid_db()

    order = await order_service.create_register_order(db, 7, 3, 5, 4, "text")

    assert order.user_id == 7
    assert order.patient_id == 4
    assert order.doctor_id == 3
    assert db.added == [order]
    redis.decr.assert_awaited_once_with("slot:remaining:5")


@pytest.mark.asyncio
async def test_failed_order_flush_restores_reserved_slot(monkeypatch):
    redis = AsyncMock()
    redis.decr.return_value = 2
    monkeypatch.setattr(order_service, "redis_client", redis)
    db = _valid_db(flush_error=RuntimeError("database unavailable"))

    with pytest.raises(RuntimeError, match="database unavailable"):
        await order_service.create_register_order(db, 7, 3, 5, 4, "text")

    redis.incr.assert_awaited_once_with("slot:remaining:5")
