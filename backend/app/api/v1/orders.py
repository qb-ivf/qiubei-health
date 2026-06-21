"""订单接口（M2：挂号下单 + 支付 + 排队条）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime, timezone

from ...constants import OrderStatus, Signal
from ...core.database import get_db
from ...core.security import mask_name
from ...models.order import Order
from ...models.user import Doctor, Patient
from ...schemas.order import ActiveOrderOut, OrderOut, PayCallback, PrepayOut, RegisterOrderCreate
from ...services import compliance_service, order_service, pay_service, prescription_service
from ...ws import manager, rooms
from ..deps import get_current_user, get_current_user_id

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


@router.post("/{order_id}/drug-prepay", response_model=PrepayOut)
async def drug_prepay(order_id: int, uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """药费支付下单（M6）。"""
    order = await db.get(Order, order_id)
    if not order or order.user_id != uid:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status != int(OrderStatus.PRESCRIBED):
        raise HTTPException(status_code=409, detail="处方未通过审核，暂不可支付药费")
    return pay_service.prepay(order.id, order.drug_fee_fen)


@router.post("/{order_id}/drug-pay/mock", response_model=OrderOut)
async def drug_pay_mock(order_id: int, uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """开发用：药费支付成功（5→6 + 分账）。"""
    try:
        order = await order_service.mark_drug_paid(db, order_id)
        await db.commit()
        await db.refresh(order)
    except order_service.StateError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    return order


@router.post("/{order_id}/refund", response_model=OrderOut)
async def refund(order_id: int, uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """申请退款（M7）：WAITING/CONSULTING/PRESCRIBED → REFUNDED。"""
    order = await db.get(Order, order_id)
    if not order or order.user_id != uid:
        raise HTTPException(status_code=404, detail="订单不存在")
    try:
        order = await order_service.refund(db, order_id, uid)
        await db.commit()
        await db.refresh(order)
    except order_service.StateError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    return order


@router.get("/{order_id}/logistics")
async def logistics(order_id: int, uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """订单物流时间轴（M7）。"""
    order = await db.get(Order, order_id)
    if not order or order.user_id != uid:
        raise HTTPException(status_code=404, detail="订单不存在")
    paid = order.status == int(OrderStatus.FINISHED)
    steps = ["已支付药费", "药房配药", "已发货", "配送中", "已签收"]
    cur = 2 if paid else -1  # 演示：支付后推进到「已发货」
    timeline = [{"t": s, "done": i <= cur} for i, s in enumerate(steps)]
    rx = await prescription_service.get_by_order(db, order_id)
    drugs = [{"name": it.get("name"), "qty": it.get("qty", 1)} for it in (rx.items if rx else [])]
    return {"paid": paid, "timeline": timeline, "drugs": drugs}


@router.get("/queue")
async def doctor_queue(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """医生候诊队列：候诊中(WAITING)订单，按下单时间升序（PRD §3.2）。

    MVP：返回全部候诊订单（开发演示）；生产按 doctor_id 过滤。
    """
    if user.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="仅医生可访问")
    res = await db.execute(
        select(Order).where(Order.status == int(OrderStatus.WAITING)).order_by(Order.id.asc())
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    out = []
    for o in res.scalars().all():
        patient = await db.get(Patient, o.patient_id)
        waited = int((now - o.created_at).total_seconds() // 60) if o.created_at else 0
        out.append({
            "order_id": o.id,
            "no": o.order_no[-3:],
            "patient_name": mask_name(patient.name) if patient else "患者",
            "gender": patient.gender if patient else None,
            "wait_minutes": max(waited, 0),
        })
    return out


@router.post("/{order_id}/accept")
async def accept(order_id: int, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """医生立即接诊：WAITING→CONSULTING + 向患者推 CALL_INVITE（PRD §2.1/§2.2）。"""
    if user.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="仅医生可接诊")
    try:
        order = await order_service.transition(
            db, order_id, OrderStatus.CONSULTING, expect_from=OrderStatus.WAITING
        )
        room_id = f"room_{order_id}"
        order.room_id = room_id
        await compliance_service.enqueue(db, "consultation", order.id)  # 接诊上报卫健委
        await db.commit()
    except order_service.StateError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(e))

    doctor_uid = int(user["sub"])
    rooms[room_id] = {"patient": order.user_id, "doctor": doctor_uid}
    doctor = await db.get(Doctor, order.doctor_id)
    await manager.send(order.user_id, {
        "type": Signal.CALL_INVITE,
        "roomId": room_id,
        "doctorName": doctor.name if doctor else "医生",
    })
    return {"room_id": room_id, "invited": order.user_id in manager.active}


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
