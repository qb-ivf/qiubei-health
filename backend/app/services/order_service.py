"""订单状态机服务（PRD §2.1 / 步战术2）。

核心：封闭式状态机 + 悲观锁 + 幂等回调。所有状态变更必须经 transition()，
严禁前端或其它 service 直接写 status 字段。
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import ALLOWED_TRANSITIONS, OrderStatus
from ..models.order import Order


class StateError(Exception):
    """非法状态迁移。"""


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
    # TODO: 写入 Redis 排队队列 room:queue:[doctor_id]
    return order
