"""财务可对账但不可读取患者主诉、诊断、医嘱等临床内容。"""
from datetime import datetime
from types import SimpleNamespace

import pytest

from app.api.v1.admin import order_detail
from app.models.order import Order
from app.models.user import Doctor, Patient


class _Result:
    def __init__(self, value):
        self.value = value

    def scalars(self):
        return self

    def first(self):
        return self.value


class _Db:
    def __init__(self):
        now = datetime(2026, 7, 26, 10, 0)
        self.order = SimpleNamespace(
            id=9,
            order_no="QBTEST9",
            patient_id=31,
            doctor_id=41,
            consult_type="text",
            register_fee_fen=1000,
            drug_fee_fen=0,
            status=6,
            created_at=now,
            updated_at=now,
        )
        self.patient = SimpleNamespace(name="患者甲")
        self.doctor = SimpleNamespace(name="医生乙", dept="内科")
        self.prescription = SimpleNamespace(
            id=51,
            diagnosis="敏感诊断",
            chief="敏感主诉",
            present_illness="敏感现病史",
            advice="敏感医嘱",
            items=[{"name": "敏感药品"}],
            audit_status="approved",
            reject_reason=None,
        )

    async def get(self, model, key):
        if model is Order:
            return self.order
        if model is Patient:
            return self.patient
        if model is Doctor:
            return self.doctor
        return None

    async def execute(self, _statement):
        return _Result(self.prescription)


@pytest.mark.asyncio
async def test_finance_order_detail_hides_clinical_information():
    data = await order_detail(9, user={"role": "finance"}, db=_Db())

    assert data["clinical_hidden"] is True
    assert data["has_prescription"] is True
    assert data["prescription"] is None
    assert "敏感" not in str(data)


@pytest.mark.asyncio
async def test_admin_order_detail_keeps_clinical_information():
    data = await order_detail(9, user={"role": "admin"}, db=_Db())

    assert data["clinical_hidden"] is False
    assert data["prescription"]["diagnosis"] == "敏感诊断"
