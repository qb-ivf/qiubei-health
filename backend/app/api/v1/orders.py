"""订单接口（M2：挂号下单 + 支付 + 排队条）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...constants import OrderStatus
from ...core.database import get_db
from ...models.order import Order
from ...models.user import Doctor
from ...schemas.order import ActiveOrderOut, OrderOut, PayCallback, PrepayOut, RegisterOrderCreate
from ...services import order_service, pay_service
from ..deps import get_current_user_id

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("/register", response_model=OrderOut)
async def create_register_order(
    body: RegisterOrderCreate, uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
):
    """挂号下单（号源锁，PENDING）。"""
    try:
        order = await order_service.create_register_order(
            db, uid, body.doctor_id, body.slot_id, body.patient_id
        )
        await db.commit()
        await db.refresh(order)
    except order_service.StateError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    return order


@router.post("/{order_id}/prepay", response_model=PrepayOut)
async def prepay(order_id: int, uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """微信支付下单，返回五元组（mock）。"""
    order = await db.get(Order, order_id)
    if not order or order.user_id != uid:
        raise HTTPException(status_code=404, detail="订单不存在")
    return pay_service.prepay(order.id, order.register_fee_fen)


@router.post("/{order_id}/pay/mock", response_model=OrderOut)
async def pay_mock(order_id: int, uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """开发用：跳过真实微信支付，直接标记支付成功（0→1）。"""
    try:
        order = await order_service.mark_paid(db, order_id)
        await db.commit()
        await db.refresh(order)
    except order_service.StateError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    return order


@router.post("/pay/callback")
async def pay_callback(body: PayCallback, db: AsyncSession = Depends(get_db)):
    """微信支付正式回调：幂等 PENDING→WAITING（验签解密后调用）。"""
    try:
        order = await order_service.handle_pay_callback(db, body.order_no)
        await db.commit()
    except order_service.StateError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    return {"code": 0, "status": order.status}


@router.get("/active", response_model=ActiveOrderOut)
async def active_order(uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """当前进行中订单（首页黄色排队条用）。"""
    active = [int(OrderStatus.WAITING), int(OrderStatus.CONSULTING)]
    res = await db.execute(
        select(Order).where(Order.user_id == uid, Order.status.in_(active)).order_by(Order.id.desc())
    )
    order = res.scalars().first()
    if not order:
        return ActiveOrderOut(has=False)
    doctor = await db.get(Doctor, order.doctor_id)
    return ActiveOrderOut(has=True, status=order.status, doctor_name=doctor.name if doctor else None)
