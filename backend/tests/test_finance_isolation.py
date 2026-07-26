"""医生钱包必须按医生隔离，提现金额必须精确到分。"""
from types import SimpleNamespace

import pytest

from app.models.withdrawal import Withdrawal
from app.services import finance_service


class _Result:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _Db:
    def __init__(self, scalar_values=(), doctor=None):
        self.scalar_values = list(scalar_values)
        self.doctor = doctor
        self.scalar_statements = []
        self.execute_statements = []
        self.added = []

    async def scalar(self, statement):
        self.scalar_statements.append(statement)
        return self.scalar_values.pop(0)

    async def execute(self, statement):
        self.execute_statements.append(statement)
        return _Result(self.doctor)

    def add(self, value):
        self.added.append(value)

    async def flush(self):
        return None


@pytest.mark.asyncio
async def test_record_ledger_is_idempotent():
    existing = SimpleNamespace(id=8, order_id=9)
    db = _Db(scalar_values=[existing])
    order = SimpleNamespace(
        id=9,
        register_fee_fen=1000,
        drug_fee_fen=0,
    )

    ledger = await finance_service.record_ledger(db, order)

    assert ledger is existing
    assert db.added == []


@pytest.mark.asyncio
async def test_wallet_filters_earnings_and_withdrawals_by_doctor():
    db = _Db(scalar_values=[101, 6000, 1000])

    balance = await finance_service.doctor_balance_fen(db, uid=7)

    assert balance == 5000
    earnings_sql = str(db.scalar_statements[1])
    locked_sql = str(db.scalar_statements[2])
    assert "JOIN orders" in earnings_sql
    assert "orders.doctor_id" in earnings_sql
    assert "withdrawals.doctor_uid" in locked_sql


@pytest.mark.asyncio
async def test_withdrawal_uses_real_doctor_name_and_locks_doctor_row():
    doctor = SimpleNamespace(id=101, user_id=7, name="测试医生")
    db = _Db(scalar_values=[6000, 1000], doctor=doctor)

    withdrawal = await finance_service.create_withdrawal(db, uid=7, amount_fen=5000)

    assert isinstance(withdrawal, Withdrawal)
    assert withdrawal.doctor_uid == 7
    assert withdrawal.doctor_name == "测试医生"
    assert withdrawal.amount_fen == 5000
    assert db.added == [withdrawal]
    assert "FOR UPDATE" in str(db.execute_statements[0])


@pytest.mark.asyncio
async def test_withdrawal_cannot_use_another_doctors_pool():
    doctor = SimpleNamespace(id=101, user_id=7, name="测试医生")
    db = _Db(scalar_values=[3000, 500], doctor=doctor)

    with pytest.raises(finance_service.FinanceError, match="超过可提现余额"):
        await finance_service.create_withdrawal(db, uid=7, amount_fen=3000)

    assert db.added == []


@pytest.mark.parametrize(
    ("amount", "expected"),
    [("0.01", 1), ("12.30", 1230), (12.3, 1230), (100, 10000)],
)
def test_yuan_to_fen_is_exact(amount, expected):
    assert finance_service.yuan_to_fen(amount) == expected


@pytest.mark.parametrize("amount", [0, "-1", "0.001", "NaN", "Infinity", "abc"])
def test_yuan_to_fen_rejects_invalid_amount(amount):
    with pytest.raises(finance_service.FinanceError):
        finance_service.yuan_to_fen(amount)
