"""订单相关接口（子系统1 示例）。"""
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...constants import OrderStatus
from ...core.database import get_db
from ...models.order import Order
from ...schemas.order import OrderCreate, OrderOut, PayCallback
from ...services import order_service

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderOut)
async def create_order(body: OrderCreate, db: AsyncSession = Depends(get_db)):
    order = Order(
        order_no="REG" + uuid.uuid4().hex[:16].upper(),
        patient_id=body.patient_id,
        doctor_id=body.doctor_id,
        register_fee_fen=body.register_fee_fen,
        status=int(OrderStatus.PENDING),
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)
    return order


@router.post("/pay/callback")
async def pay_callback(body: PayCallback, db: AsyncSession = Depends(get_db)):
    """微信支付回调：幂等地 PENDING -> WAITING。"""
    try:
        order = await order_service.handle_pay_callback(db, body.order_no)
        await db.commit()
    except order_service.StateError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    return {"code": 0, "status": order.status}


@router.post("/{order_id}/accept", response_model=OrderOut)
async def accept(order_id: int, db: AsyncSession = Depends(get_db)):
    """医生立即接诊：WAITING -> CONSULTING。"""
    try:
        order = await order_service.transition(
            db, order_id, OrderStatus.CONSULTING, expect_from=OrderStatus.WAITING
        )
        await db.commit()
    except order_service.StateError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    return order
