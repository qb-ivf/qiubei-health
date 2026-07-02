"""订单接口（M2：挂号下单 + 支付 + 排队条）。"""
import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import datetime, timezone

from ...constants import OrderStatus, Signal
from ...core.database import get_db
from ...core.security import mask_name
from ...models.order import Order
from ...models.user import Doctor, Patient, User
from ...schemas.evaluation import EvaluationCreate, EvaluationOut
from ...schemas.order import ActiveOrderOut, OrderOut, PrepayOut, RegisterOrderCreate
from ...services import compliance_service, evaluation_service, order_service, pay_service, prescription_service
from ...ws import manager, rooms
from ..deps import get_current_user_id, require_approved_doctor

router = APIRouter(prefix="/orders", tags=["orders"])
logger = logging.getLogger("orders")


@router.post("/register", response_model=OrderOut)
async def create_register_order(
    body: RegisterOrderCreate, uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
):
    """挂号下单（号源锁，PENDING）。"""
    try:
        order = await order_service.create_register_order(
            db, uid, body.doctor_id, body.slot_id, body.patient_id, body.consult_type
        )
        await db.commit()
        await db.refresh(order)
    except order_service.StateError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    return order


@router.post("/{order_id}/prepay", response_model=PrepayOut)
async def prepay(order_id: int, uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """挂号费微信支付下单，返回 wx.requestPayment 五元组（未配凭据则 mock）。"""
    order = await db.get(Order, order_id)
    if not order or order.user_id != uid:
        raise HTTPException(status_code=404, detail="订单不存在")
    user = await db.get(User, uid)
    try:
        return await pay_service.prepay(
            order.order_no, order.register_fee_fen,
            openid=user.openid if user else "", description="互联网医院挂号费", order_id=order.id,
        )
    except pay_service.PayError as e:
        raise HTTPException(status_code=502, detail=str(e))


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
async def pay_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """微信支付 V3 结果通知：验签 + 解密 → 幂等推进订单。

    返回体须为 {"code":"SUCCESS"} 且 HTTP 200，否则微信会重试。
    未启用真实支付时（开发），兼容旧的 {order_no} 直推（仅供本地联调）。
    """
    body = (await request.body()).decode()
    try:
        transaction_id = None
        if pay_service.is_enabled():
            resource = await pay_service.verify_and_decrypt(request.headers, body)
            if resource.get("trade_state") != "SUCCESS":
                return {"code": "SUCCESS", "message": "OK"}  # 非成功态：已接收，不处理
            out_trade_no = resource["out_trade_no"]
            transaction_id = resource.get("transaction_id")  # 微信流水号（监管核销 tradeNo）
        else:
            out_trade_no = (json.loads(body) if body else {}).get("order_no")
            if not out_trade_no:
                raise HTTPException(status_code=400, detail="缺少 order_no")

        if out_trade_no.endswith(pay_service.DRUG_SUFFIX):
            await order_service.mark_drug_paid_by_no(
                db, out_trade_no[: -len(pay_service.DRUG_SUFFIX)], transaction_id
            )
        else:
            await order_service.handle_pay_callback(db, out_trade_no, transaction_id)
        await db.commit()
    except pay_service.PayError as e:
        await db.rollback()
        logger.warning("支付回调验签/解密失败: %s", e)
        return JSONResponse(status_code=401, content={"code": "FAIL", "message": str(e)})
    except order_service.StateError as e:
        await db.rollback()
        logger.error("支付回调处理失败: %s", e)
        return JSONResponse(status_code=500, content={"code": "FAIL", "message": str(e)})
    return {"code": "SUCCESS", "message": "OK"}


@router.post("/{order_id}/drug-prepay", response_model=PrepayOut)
async def drug_prepay(order_id: int, uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """药费支付下单（M6）。"""
    order = await db.get(Order, order_id)
    if not order or order.user_id != uid:
        raise HTTPException(status_code=404, detail="订单不存在")
    if order.status != int(OrderStatus.PRESCRIBED):
        raise HTTPException(status_code=409, detail="处方未通过审核，暂不可支付药费")
    user = await db.get(User, uid)
    try:
        return await pay_service.prepay(
            order.order_no + pay_service.DRUG_SUFFIX, order.drug_fee_fen,
            openid=user.openid if user else "", description="互联网医院药费", order_id=order.id,
        )
    except pay_service.PayError as e:
        raise HTTPException(status_code=502, detail=str(e))


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


@router.post("/{order_id}/evaluation", response_model=EvaluationOut)
async def create_evaluation(
    order_id: int, body: EvaluationCreate, uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
):
    """患者评价（订单完成/退款后，一单一评；数据用于监管 2.4.1 上报）。"""
    try:
        ev = await evaluation_service.create(db, uid, order_id, body)
        await db.commit()
        await db.refresh(ev)
    except evaluation_service.EvalError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    return ev


@router.get("/{order_id}/evaluation", response_model=EvaluationOut | None)
async def get_evaluation(order_id: int, uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """查询订单评价（小程序判断是否已评价，未评价返回 null）。"""
    order = await db.get(Order, order_id)
    if not order or order.user_id != uid:
        raise HTTPException(status_code=404, detail="订单不存在")
    return await evaluation_service.get_by_order(db, order_id)


@router.get("/queue")
async def doctor_queue(user=Depends(require_approved_doctor), db: AsyncSession = Depends(get_db)):
    """医生候诊队列：本医生名下候诊中(WAITING)订单，按下单时间升序（PRD §3.2）。"""
    res = await db.execute(select(Doctor.id).where(Doctor.user_id == int(user["sub"])))
    doctor_id = res.scalar_one_or_none()
    res = await db.execute(
        select(Order)
        .where(Order.status == int(OrderStatus.WAITING), Order.doctor_id == doctor_id)
        .order_by(Order.id.asc())
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
async def accept(order_id: int, user=Depends(require_approved_doctor), db: AsyncSession = Depends(get_db)):
    """医生立即接诊：WAITING→CONSULTING + 向患者推 CALL_INVITE（PRD §2.1/§2.2）。"""
    # 仅可接诊分配给本医生的订单
    res = await db.execute(select(Doctor.id).where(Doctor.user_id == int(user["sub"])))
    my_doctor_id = res.scalar_one_or_none()
    target = await db.get(Order, order_id)
    if not target or target.doctor_id != my_doctor_id:
        raise HTTPException(status_code=404, detail="订单不存在或不属于您")
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
    if order.consult_type == "text":
        # 图文：不推视频呼叫；通知患者医生已接诊（患者在聊天页等待）
        await manager.send(order.user_id, {"type": Signal.CHAT_MESSAGE, "orderId": order.id, "msg": None})
    else:
        await manager.send(order.user_id, {
            "type": Signal.CALL_INVITE,
            "roomId": room_id,
            "doctorName": doctor.name if doctor else "医生",
        })
    return {
        "room_id": room_id,
        "consult_type": order.consult_type,
        "invited": order.user_id in manager.active,
    }


@router.post("/{order_id}/end-consult")
async def end_consult(order_id: int, user=Depends(require_approved_doctor), db: AsyncSession = Depends(get_db)):
    """医生挂断结束问诊：CONSULTING→FINISHED（无处方）。让订单离开进行中状态，
    避免患者端"离线补偿"把它当作进行中而反复拉回呼叫。仅本医生可操作；非 CONSULTING 则忽略。"""
    res = await db.execute(select(Doctor.id).where(Doctor.user_id == int(user["sub"])))
    my_doctor_id = res.scalar_one_or_none()
    target = await db.get(Order, order_id)
    if not target or target.doctor_id != my_doctor_id:
        raise HTTPException(status_code=404, detail="订单不存在或不属于您")
    if target.status == int(OrderStatus.CONSULTING):
        try:
            target = await order_service.transition(
                db, order_id, OrderStatus.FINISHED, expect_from=OrderStatus.CONSULTING
            )
            await db.commit()
        except order_service.StateError as e:
            await db.rollback()
            raise HTTPException(status_code=409, detail=str(e))
    return {"status": target.status}


@router.get("/mine")
async def my_orders(status: int | None = None, uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """患者本人订单列表（我的问诊）。可选 status 过滤。"""
    stmt = select(Order).where(Order.user_id == uid)
    if status is not None:
        stmt = stmt.where(Order.status == status)
    res = await db.execute(stmt.order_by(Order.id.desc()))
    out = []
    for o in res.scalars().all():
        doctor = await db.get(Doctor, o.doctor_id)
        out.append({
            "id": o.id, "order_no": o.order_no, "status": o.status,
            "consult_type": getattr(o, "consult_type", "video"),
            "doctor_name": doctor.name if doctor else None,
            "dept": doctor.dept if doctor else None,
            "register_fee_fen": o.register_fee_fen, "room_id": o.room_id,
            "created_at": o.created_at,
        })
    return out


@router.get("/doctor-mine")
async def doctor_orders(status: int | None = None, user=Depends(require_approved_doctor), db: AsyncSession = Depends(get_db)):
    """医生本人接诊订单列表（接诊记录）。可选 status 过滤。"""
    res = await db.execute(select(Doctor.id).where(Doctor.user_id == int(user["sub"])))
    doctor_id = res.scalar_one_or_none()
    stmt = select(Order).where(Order.doctor_id == doctor_id)
    if status is not None:
        stmt = stmt.where(Order.status == status)
    res = await db.execute(stmt.order_by(Order.id.desc()))
    out = []
    for o in res.scalars().all():
        patient = await db.get(Patient, o.patient_id)
        out.append({
            "id": o.id, "status": o.status,
            "consult_type": getattr(o, "consult_type", "video"),
            "patient_name": mask_name(patient.name) if patient and patient.name else "患者",
            "gender": patient.gender if patient else None,
            "room_id": o.room_id,
        })
    return out


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
    return ActiveOrderOut(
        has=True, status=order.status, doctor_name=doctor.name if doctor else None,
        room_id=order.room_id, order_id=order.id,
    )
