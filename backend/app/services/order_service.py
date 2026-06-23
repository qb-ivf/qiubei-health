"""订单状态机服务（PRD §2.1 / 步战术2）。

核心：封闭式状态机 + 悲观锁 + 幂等回调。所有状态变更必须经 transition()，
严禁前端或其它 service 直接写 status 字段。
"""
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import ALLOWED_TRANSITIONS, OrderStatus
from ..core.redis import redis_client
from ..models.order import Order
from ..models.schedule import Slot
from ..models.user import Doctor


class StateError(Exception):
    """非法状态迁移。"""


def _slot_key(slot_id: int) -> str:
    return f"slot:remaining:{slot_id}"


async def create_register_order(db: AsyncSession, user_id: int, doctor_id: int, slot_id: int, patient_id: int) -> Order:
    """创建挂号订单：Redis 号源锁（DECR 防超卖）+ PENDING。"""
    doctor = await db.get(Doctor, doctor_id)
    if doctor is None:
        raise StateError("医生不存在")

    # 号源锁：DECR < 0 则回补并报无号
    left = await redis_client.decr(_slot_key(slot_id))
    if left < 0:
        await redis_client.incr(_slot_key(slot_id))
        raise StateError("该时段号源已约满")

    order = Order(
        order_no="REG" + uuid.uuid4().hex[:16].upper(),
        user_id=user_id, patient_id=patient_id, doctor_id=doctor_id, slot_id=slot_id,
        register_fee_fen=doctor.register_fee_fen, status=int(OrderStatus.PENDING),
    )
    db.add(order)
    await db.flush()
    return order


def can_transition(cur: OrderStatus, to: OrderStatus) -> bool:
    return to in ALLOWED_TRANSITIONS.get(cur, set())


async def transition(
    db: AsyncSession, order_id: int, to: OrderStatus, expect_from: OrderStatus | None = None
) -> Order:
    """通用状态迁移：SELECT ... FOR UPDATE 锁行 → 校验白名单 → 变更。"""
    res = await db.execute(select(Order).where(Order.id == order_id).with_for_update())
    order = res.scalar_one_or_none()
    if order is None:
        raise StateError("订单不存在")

    cur = OrderStatus(order.status)
    if expect_from is not None and cur != expect_from:
        raise StateError(f"当前状态 {cur.name} 与期望 {expect_from.name} 不符")
    if not can_transition(cur, to):
        raise StateError(f"非法迁移 {cur.name} -> {to.name}")

    order.status = int(to)
    await db.flush()
    return order


async def handle_pay_callback(db: AsyncSession, order_no: str) -> Order:
    """微信支付回调：幂等。锁行后仅当 PENDING 才置 WAITING（PRD §2.1 技术需求）。"""
    res = await db.execute(
        select(Order).where(Order.order_no == order_no).with_for_update()
    )
    order = res.scalar_one_or_none()
    if order is None:
        raise StateError("订单不存在")

    if order.status != int(OrderStatus.PENDING):
        # 幂等：重复回调直接返回，不重复处理
        return order

    order.status = int(OrderStatus.WAITING)
    await db.flush()
    await redis_client.rpush(f"room:queue:{order.doctor_id}", order.id)  # 进排队队列
    await _notify(db, order.user_id, "order", "挂号成功", "请保持手机亮屏，等待医生接诊", order.id)
    return order


async def _notify(db, uid, ntype, title, body, order_id):
    from . import notification_service  # 局部导入避免循环
    await notification_service.notify(db, uid, ntype, title, body, order_id)


async def mark_paid(db: AsyncSession, order_id: int) -> Order:
    """按订单 ID 标记支付成功（mock 支付/真实回调通用）：锁行 + 幂等 0→1。"""
    res = await db.execute(select(Order).where(Order.id == order_id).with_for_update())
    order = res.scalar_one_or_none()
    if order is None:
        raise StateError("订单不存在")
    if order.status != int(OrderStatus.PENDING):
        return order  # 幂等
    order.status = int(OrderStatus.WAITING)
    await db.flush()
    await redis_client.rpush(f"room:queue:{order.doctor_id}", order.id)
    await _notify(db, order.user_id, "order", "挂号成功", "请保持手机亮屏，等待医生接诊", order.id)
    return order


async def refund(db: AsyncSession, order_id: int, operator_uid: int | None = None) -> Order:
    """退款（M7）：WAITING/CONSULTING/PRESCRIBED → REFUNDED；候诊未接诊则回补号源。"""
    res = await db.execute(select(Order).where(Order.id == order_id).with_for_update())
    order = res.scalar_one_or_none()
    if order is None:
        raise StateError("订单不存在")
    cur = OrderStatus(order.status)
    if not can_transition(cur, OrderStatus.REFUNDED):
        raise StateError(f"当前状态 {cur.name} 不可退款")
    order.status = int(OrderStatus.REFUNDED)
    if cur == OrderStatus.WAITING and order.slot_id:
        await redis_client.incr(_slot_key(order.slot_id))  # 回补号源
    await db.flush()
    await _notify(db, order.user_id, "refund", "订单已退款", "退款将原路返回，请留意账户", order.id)
    return order


async def mark_drug_paid(db: AsyncSession, order_id: int) -> Order:
    """药费支付成功：锁行 + 幂等 PRESCRIBED→FINISHED + 写分账（M6）。"""
    from . import finance_service  # 局部导入避免循环

    res = await db.execute(select(Order).where(Order.id == order_id).with_for_update())
    order = res.scalar_one_or_none()
    if order is None:
        raise StateError("订单不存在")
    if order.status == int(OrderStatus.FINISHED):
        return order  # 幂等
    if order.status != int(OrderStatus.PRESCRIBED):
        raise StateError(f"当前状态 {OrderStatus(order.status).name} 不可支付药费")
    order.status = int(OrderStatus.FINISHED)
    await db.flush()
    await finance_service.record_ledger(db, order)
    await _notify(db, order.user_id, "logistics", "药品已发货", "您的药品正在配送途中，请留意签收", order.id)
    return order


async def mark_drug_paid_by_no(db: AsyncSession, order_no: str) -> Order:
    """按 order_no 标记药费支付成功（真实回调用，out_trade_no 去掉后缀后传入）。"""
    res = await db.execute(select(Order.id).where(Order.order_no == order_no))
    oid = res.scalar_one_or_none()
    if oid is None:
        raise StateError("订单不存在")
    return await mark_drug_paid(db, oid)


async def cancel_expired(db: AsyncSession) -> int:
    """扫描超 15 分钟未支付的订单 → CANCELLED，并回补号源。"""
    deadline = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=15)
    res = await db.execute(
        select(Order).where(Order.status == int(OrderStatus.PENDING), Order.created_at < deadline)
    )
    orders = res.scalars().all()
    for o in orders:
        o.status = int(OrderStatus.CANCELLED)
        if o.slot_id:
            await redis_client.incr(_slot_key(o.slot_id))  # 回补号源
    if orders:
        await db.commit()
    return len(orders)
