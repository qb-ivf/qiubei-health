"""财务分账（PRD §4.3）。金额一律用「分」整数运算，避免精度误差。"""
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.ledger import Ledger
from ..models.order import Order
from ..models.withdrawal import Withdrawal

# 分账比例：平台技术服务费 / 医生分成 / 医院留存（余额归医院，防舍入丢分）
PLATFORM_PCT = 10
DOCTOR_PCT = 60


def split(total_fen: int) -> tuple[int, int, int]:
    platform = total_fen * PLATFORM_PCT // 100
    doctor = total_fen * DOCTOR_PCT // 100
    hospital = total_fen - platform - doctor
    return hospital, doctor, platform


async def record_ledger(db: AsyncSession, order: Order) -> Ledger:
    total = order.register_fee_fen + order.drug_fee_fen
    hospital, doctor, platform = split(total)
    led = Ledger(
        order_id=order.id, total_fen=total,
        hospital_fen=hospital, doctor_fen=doctor, platform_fen=platform,
    )
    db.add(led)
    await db.flush()
    return led


# —— 医生钱包 / 提现（M8）——
class FinanceError(Exception):
    pass


async def doctor_balance_fen(db: AsyncSession) -> int:
    """演示用池化余额 = 全部医生分成 − 冻结/已打款提现。生产应按医生维度核算。"""
    total = await db.scalar(select(func.coalesce(func.sum(Ledger.doctor_fen), 0)))
    locked = await db.scalar(
        select(func.coalesce(func.sum(Withdrawal.amount_fen), 0)).where(Withdrawal.status.in_(["pending", "paid"]))
    )
    return int(total) - int(locked)


async def create_withdrawal(db: AsyncSession, uid: int, name: str | None, amount_fen: int) -> Withdrawal:
    if amount_fen <= 0:
        raise FinanceError("提现金额需大于 0")
    if amount_fen > await doctor_balance_fen(db):
        raise FinanceError("提现金额超过可提现余额")
    w = Withdrawal(doctor_uid=uid, doctor_name=name, amount_fen=amount_fen, status="pending")
    db.add(w)
    await db.flush()
    return w


async def list_withdrawals(db: AsyncSession) -> list[Withdrawal]:
    res = await db.execute(select(Withdrawal).order_by(Withdrawal.id.desc()))
    return list(res.scalars().all())


async def set_withdrawal_status(db: AsyncSession, wid: int, status: str) -> Withdrawal:
    w = await db.get(Withdrawal, wid)
    if w is None or w.status != "pending":
        raise FinanceError("提现单不存在或已处理")
    w.status = status  # paid（调微信商家转账成功）/ rejected（解冻）
    await db.flush()
    return w
