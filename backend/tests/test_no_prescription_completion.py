"""无药问诊必须保存病历并完成，不能生成空处方或进入药师审方。"""
from types import SimpleNamespace

import pytest

from app.constants import OrderStatus
from app.core.config import settings
from app.models.order import Order
from app.models.prescription import Prescription
from app.schemas.prescription import MedicalRecordComplete, PrescriptionCreate
from app.services import notification_service, order_service, prescription_service


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def first(self):
        return self.value


class _Db:
    def __init__(self, order, doctor):
        self.order = order
        self.results = [order, doctor, None]
        self.added = []
        self.flushes = 0

    async def get(self, _model, _key):
        return None

    async def execute(self, _query):
        return _Result(self.results.pop(0))

    def add(self, value):
        if isinstance(value, Prescription) and value.id is None:
            value.id = 51
        self.added.append(value)

    async def flush(self):
        self.flushes += 1


@pytest.mark.asyncio
async def test_empty_drug_list_is_not_an_electronic_prescription():
    data = PrescriptionCreate(
        order_id=1,
        chief="咽痛两天",
        present_illness="咽痛两天，无呼吸困难",
        diagnosis="上呼吸道感染",
        items=[],
    )

    with pytest.raises(prescription_service.RxError, match="至少应包含一种药品"):
        await prescription_service.submit(None, 7, data)


@pytest.mark.asyncio
async def test_complete_without_prescription_saves_emr_and_skips_pharmacy(monkeypatch):
    order = SimpleNamespace(
        id=9,
        user_id=21,
        patient_id=31,
        doctor_id=41,
        status=int(OrderStatus.CONSULTING),
    )
    doctor = SimpleNamespace(id=41, name="医师甲", id_card_enc=None)
    db = _Db(order, doctor)
    notices = []

    async def transition(_db, order_id, to, expect_from=None):
        assert order_id == order.id
        assert to == OrderStatus.FINISHED
        assert expect_from == OrderStatus.CONSULTING
        order.status = int(to)
        return order

    async def notify(_db, user_id, ntype, title, body="", order_id=None):
        notices.append((user_id, ntype, title, body, order_id))

    monkeypatch.setattr(settings, "FXQ_CA_REQUIRED", False)
    monkeypatch.setattr(settings, "FXQ_DOCUMENT_SIGN_ENABLED", False)
    monkeypatch.setattr(order_service, "transition", transition)
    monkeypatch.setattr(notification_service, "notify", notify)

    record = await prescription_service.complete_without_prescription(
        db,
        doctor_uid=7,
        order_id=order.id,
        data=MedicalRecordComplete(
            chief="咽痛两天",
            present_illness="咽痛两天，无呼吸困难",
            diagnosis="急性上呼吸道感染",
            advice="休息、补水，症状加重及时线下就诊",
            icd_code="J06.9",
            icd_name="急性上呼吸道感染",
        ),
    )

    assert record.audit_status == "not_required"
    assert record.items == []
    assert record.diagnosis == "急性上呼吸道感染"
    assert record.ca_sign_status is None
    assert order.status == int(OrderStatus.FINISHED)
    assert notices[0][0] == order.user_id
    assert "未开具药品" in notices[0][3]
