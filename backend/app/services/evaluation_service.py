"""评价服务（天津监管 2.4.1 数据源，S2）：一单一评 + 入监管上报队列。"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import OrderStatus
from ..models.evaluation import Evaluation
from ..models.order import Order
from ..models.user import Patient
from ..schemas.evaluation import EvaluationCreate
from . import compliance_service

# 允许评价的终态：完成 / 已退款（退款单的差评同样是监管关心的数据）
_EVALUABLE = {int(OrderStatus.FINISHED), int(OrderStatus.REFUNDED)}


class EvalError(Exception):
    """评价业务异常。"""


async def create(db: AsyncSession, uid: int, order_id: int, data: EvaluationCreate) -> Evaluation:
    order = await db.get(Order, order_id)
    if order is None or order.user_id != uid:
        raise EvalError("订单不存在")
    if order.status not in _EVALUABLE:
        raise EvalError("订单完成后才可评价")
    existing = await get_by_order(db, order_id)
    if existing:
        raise EvalError("该订单已评价")

    patient = await db.get(Patient, order.patient_id)
    ev = Evaluation(
        order_id=order_id,
        user_id=uid,
        doctor_id=order.doctor_id,
        satisfaction=data.satisfaction,
        scoring=data.scoring,
        content=data.content,
        complaints=data.complaints,
        evaluator=patient.name if patient else None,
    )
    db.add(ev)
    await db.flush()
    await compliance_service.enqueue(db, "evaluation", ev.id)  # 评价上报监管平台（S3 映射发送）
    return ev


async def get_by_order(db: AsyncSession, order_id: int) -> Evaluation | None:
    res = await db.execute(select(Evaluation).where(Evaluation.order_id == order_id))
    return res.scalars().first()
