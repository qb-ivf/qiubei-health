"""财务分账（PRD §4.3）。金额一律用「分」整数运算，避免精度误差。"""
from decimal import Decimal, InvalidOperation

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.user import Doctor
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
    existing = await db.scalar(
        select(Ledger).where(Ledger.order_id == order.id)
    )
    if existing is not None:
        return existing
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


def yuan_to_fen(amount: object) -> int:
    """人民币元转分；拒绝非有限数和超过两位小数，避免静默舍入资金。"""
    try:
        value = Decimal(str(amount))
    except (InvalidOperation, ValueError):
        raise FinanceError("提现金额格式不正确") from None
    if not value.is_finite() or value.as_tuple().exponent < -2:
        raise FinanceError("提现金额最多保留两位小数")
    amount_fen = int(value * 100)
    if amount_fen <= 0:
        raise FinanceError("提现金额需大于 0")
    return amount_fen


async def _doctor_earnings_fen(db: AsyncSession, doctor_id: int) -> int:
    total = await db.scalar(
        select(func.coalesce(func.sum(Ledger.doctor_fen), 0))
        .join(Order, Ledger.order_id == Order.id)
        .where(Order.doctor_id == doctor_id)
    )
    return int(total or 0)


async def _doctor_locked_fen(db: AsyncSession, uid: int) -> int:
    locked = await db.scalar(
        select(func.coalesce(func.sum(Withdrawal.amount_fen), 0)).where(
            Withdrawal.doctor_uid == uid,
            Withdrawal.status.in_(["pending", "paid"]),
        )
    )
    return int(locked or 0)


async def doctor_balance_fen(db: AsyncSession, uid: int) -> int:
    """医生本人可提现余额 = 本人订单分成 − 本人审核中/已打款提现。"""
    doctor_id = await db.scalar(select(Doctor.id).where(Doctor.user_id == uid))
    if doctor_id is None:
        raise FinanceError("医生档案不存在")
    return await _doctor_earnings_fen(db, int(doctor_id)) - await _doctor_locked_fen(db, uid)


async def total_doctor_balance_fen(db: AsyncSession) -> int:
    """运营看板口径：全院医生分成减去全部审核中/已打款提现。"""
    total = await db.scalar(select(func.coalesce(func.sum(Ledger.doctor_fen), 0)))
    locked = await db.scalar(
        select(func.coalesce(func.sum(Withdrawal.amount_fen), 0)).where(
            Withdrawal.status.in_(["pending", "paid"])
        )
    )
    return int(total or 0) - int(locked or 0)


async def create_withdrawal(db: AsyncSession, uid: int, amount_fen: int) -> Withdrawal:
    if amount_fen <= 0:
        raise FinanceError("提现金额需大于 0")
    # 同一医生的提现申请串行化，避免两个并发请求同时通过余额校验。
    res = await db.execute(
        select(Doctor).where(Doctor.user_id == uid).with_for_update()
    )
    doctor = res.scalar_one_or_none()
    if doctor is None:
        raise FinanceError("医生档案不存在")
    balance = await _doctor_earnings_fen(db, doctor.id) - await _doctor_locked_fen(db, uid)
    if amount_fen > balance:
        raise FinanceError("提现金额超过可提现余额")
    w = Withdrawal(
        doctor_uid=uid,
        doctor_name=doctor.name,
        amount_fen=amount_fen,
        status="pending",
    )
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
