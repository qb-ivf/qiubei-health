"""放心签响应不确定时，处方必须锁定到人工确认而不能重复处置。"""
from types import SimpleNamespace

import pytest

from app.models.prescription import Prescription
from app.models.staff import Staff
from app.services import prescription_service


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _Db:
    def __init__(self, rx, staff=None):
        self.rx = rx
        self.staff = staff
        self.flushes = 0

    async def execute(self, _query):
        return _Result(self.rx)

    async def get(self, model, _key):
        if model is Staff:
            return self.staff
        if model is Prescription:
            return self.rx
        return None

    async def flush(self):
        self.flushes += 1


def _rx(status=None, audit_status="pending"):
    return SimpleNamespace(id=17, audit_status=audit_status, ca_sign_status=status)


@pytest.mark.asyncio
async def test_manual_review_lock_must_be_explicitly_cleared():
    rx = _rx()
    db = _Db(rx)

    locked = await prescription_service.mark_signing_manual_review(db, rx.id)
    assert locked.ca_sign_status == "manual_review"

    cleared = await prescription_service.clear_signing_manual_review(db, rx.id)
    assert cleared.ca_sign_status == "failed"
    assert db.flushes == 2


@pytest.mark.asyncio
async def test_manual_review_lock_blocks_repeated_approval():
    rx = _rx("manual_review")
    staff = SimpleNamespace(
        id=3,
        active=True,
        name="药师乙",
        id_card_enc="encrypted",
    )

    with pytest.raises(prescription_service.RxError, match="禁止重复签署"):
        await prescription_service.approve(_Db(rx, staff), rx.id, staff_id=staff.id)

    assert rx.audit_status == "pending"
    assert rx.ca_sign_status == "manual_review"


@pytest.mark.asyncio
async def test_manual_review_lock_blocks_rejection():
    rx = _rx("manual_review")

    with pytest.raises(prescription_service.RxError, match="禁止驳回"):
        await prescription_service.reject(_Db(rx), rx.id, "改用其他药品")

    assert rx.audit_status == "pending"
    assert rx.ca_sign_status == "manual_review"


@pytest.mark.asyncio
async def test_no_prescription_record_manual_review_lock_can_be_cleared():
    rx = _rx("manual_review", audit_status="not_required")
    db = _Db(rx)

    cleared = await prescription_service.clear_signing_manual_review(db, rx.id)

    assert cleared.ca_sign_status == "failed"
    assert db.flushes == 1
