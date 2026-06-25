"""运营总管理后台接口（PRD 子系统3，M8）。需 admin 角色。"""
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.crypto import decrypt
from ...core.database import get_db
from ...core.security import mask_name, mask_phone
from ...models.drug import Drug
from ...models.ledger import Ledger
from ...models.order import Order
from ...models.prescription import Prescription
from ...models.staff import Staff
from ...models.user import Doctor, Patient, User
from ...models.withdrawal import Withdrawal
from ...services import audit_service, compliance_service, finance_service, staff_service
from ..deps import require_role

router = APIRouter(prefix="/admin", tags=["admin"])
_admin = require_role("admin")

# 订单状态文案（与 constants.OrderStatus 对齐）
ORDER_STATUS_TEXT = {
    0: "待支付", 1: "候诊中", 2: "问诊中", 3: "待审方",
    4: "审方驳回", 5: "已开方", 6: "已完成", 7: "已退款", 9: "已取消",
}


def _fmt(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


def _safe_decrypt(enc):
    if not enc:
        return None
    try:
        return decrypt(enc)
    except Exception:  # noqa: BLE001
        return None


# —— 医生资质终审（§4.1）——
@router.get("/doctors")
async def list_doctors(status: str | None = None, user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    q = select(Doctor).order_by(Doctor.id.asc())
    if status in ("pending", "approved", "rejected"):
        q = q.where(Doctor.audit_status == status)
    res = await db.execute(q)
    out = []
    for d in res.scalars().all():
        u = await db.get(User, d.user_id)
        out.append({
            "id": d.id, "name": d.name, "dept": d.dept, "title": d.title,
            "license_no": d.license_no, "practice_no": d.practice_no,
            "good_at": d.good_at, "years": d.years,
            "register_fee": d.register_fee_fen / 100,
            "phone": mask_phone(_safe_decrypt(u.phone_enc)) if u and u.phone_enc else None,
            "audit_status": d.audit_status, "created_at": _fmt(d.created_at),
        })
    return out


@router.post("/doctors/{doctor_id}/audit")
async def audit_doctor(doctor_id: int, request: Request, approve: bool = Body(embed=True), user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    d = await db.get(Doctor, doctor_id)
    if not d:
        raise HTTPException(status_code=404, detail="医生不存在")
    d.audit_status = "approved" if approve else "rejected"
    await audit_service.record(
        db, user, request, "资质终审" + ("通过" if approve else "驳回"),
        "doctor", doctor_id, f"{d.name or doctor_id} → {d.audit_status}",
    )
    await db.commit()
    return {"id": d.id, "audit_status": d.audit_status}


# —— 药品字典（§4.2）——
@router.get("/drugs")
async def list_drugs(user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Drug).order_by(Drug.id.asc()))
    return [
        {"id": x.id, "name": x.name, "spec": x.spec, "price": x.price_fen / 100,
         "category": x.category, "restricted": x.restricted}
        for x in res.scalars().all()
    ]


@router.post("/drugs")
async def add_drug(request: Request, body: dict = Body(...), user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    drug = Drug(
        name=body["name"], spec=body.get("spec"),
        price_fen=int(round(float(body.get("price", 0)) * 100)),
        category=body.get("category", "处方药"),
        restricted=bool(body.get("restricted", False)),
    )
    db.add(drug)
    await db.flush()
    await audit_service.record(db, user, request, "新增药品", "drug", drug.id, drug.name)
    await db.commit()
    return {"id": drug.id}


@router.put("/drugs/{drug_id}")
async def update_drug(drug_id: int, request: Request, body: dict = Body(...), user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    drug = await db.get(Drug, drug_id)
    if not drug:
        raise HTTPException(status_code=404, detail="药品不存在")
    if "name" in body:
        drug.name = body["name"]
    if "spec" in body:
        drug.spec = body.get("spec")
    if "price" in body:
        drug.price_fen = int(round(float(body["price"]) * 100))
    if "category" in body:
        drug.category = body["category"]
    if "restricted" in body:
        drug.restricted = bool(body["restricted"])
    await audit_service.record(db, user, request, "编辑药品", "drug", drug_id, drug.name)
    await db.commit()
    return {"id": drug.id}


@router.delete("/drugs/{drug_id}")
async def delete_drug(drug_id: int, request: Request, user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    drug = await db.get(Drug, drug_id)
    if not drug:
        raise HTTPException(status_code=404, detail="药品不存在")
    name = drug.name
    await db.delete(drug)
    await audit_service.record(db, user, request, "删除药品", "drug", drug_id, name)
    await db.commit()
    return {"ok": True}


# —— 审方历史（待审/已通过/已驳回，解决“已审核看不见”）——
@router.get("/prescriptions")
async def list_prescriptions(status: str | None = None, user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    q = select(Prescription).order_by(Prescription.id.desc()).limit(300)
    if status in ("pending", "approved", "rejected"):
        q = q.where(Prescription.audit_status == status)
    res = await db.execute(q)
    out = []
    for rx in res.scalars().all():
        doctor = await db.get(Doctor, rx.doctor_id)
        patient = await db.get(Patient, rx.patient_id)
        out.append({
            "id": rx.id, "order_id": rx.order_id,
            "patient_name": mask_name(patient.name) if patient else None,
            "doctor_name": doctor.name if doctor else None,
            "dept": doctor.dept if doctor else None,
            "diagnosis": rx.diagnosis, "items": rx.items or [],
            "chief": rx.chief, "present_illness": rx.present_illness, "advice": rx.advice,
            "audit_status": rx.audit_status, "reject_reason": rx.reject_reason,
            "created_at": _fmt(rx.created_at),
        })
    return out


# —— 订单管理（全部问诊订单可查）——
@router.get("/orders")
async def list_orders(status: int | None = None, user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    q = select(Order).order_by(Order.id.desc()).limit(300)
    if status is not None:
        q = q.where(Order.status == status)
    res = await db.execute(q)
    out = []
    for o in res.scalars().all():
        patient = await db.get(Patient, o.patient_id)
        doctor = await db.get(Doctor, o.doctor_id)
        out.append({
            "id": o.id, "order_no": o.order_no,
            "patient_name": mask_name(patient.name) if patient else None,
            "doctor_name": doctor.name if doctor else None,
            "type": "图文" if o.consult_type == "text" else "视频",
            "register_fee": o.register_fee_fen / 100, "drug_fee": o.drug_fee_fen / 100,
            "status": o.status, "status_text": ORDER_STATUS_TEXT.get(o.status, str(o.status)),
            "created_at": _fmt(o.created_at),
        })
    return out


@router.get("/orders/{order_id}")
async def order_detail(order_id: int, user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    o = await db.get(Order, order_id)
    if not o:
        raise HTTPException(status_code=404, detail="订单不存在")
    patient = await db.get(Patient, o.patient_id)
    doctor = await db.get(Doctor, o.doctor_id)
    res = await db.execute(select(Prescription).where(Prescription.order_id == order_id))
    rx = res.scalars().first()
    rx_out = None
    if rx:
        rx_out = {
            "id": rx.id, "diagnosis": rx.diagnosis, "chief": rx.chief,
            "present_illness": rx.present_illness, "advice": rx.advice,
            "items": rx.items or [], "audit_status": rx.audit_status, "reject_reason": rx.reject_reason,
        }
    return {
        "id": o.id, "order_no": o.order_no,
        "patient_name": mask_name(patient.name) if patient else None,
        "doctor_name": doctor.name if doctor else None, "dept": doctor.dept if doctor else None,
        "type": "图文咨询" if o.consult_type == "text" else "视频问诊",
        "register_fee": o.register_fee_fen / 100, "drug_fee": o.drug_fee_fen / 100,
        "total_fee": (o.register_fee_fen + o.drug_fee_fen) / 100,
        "status": o.status, "status_text": ORDER_STATUS_TEXT.get(o.status, str(o.status)),
        "created_at": _fmt(o.created_at), "updated_at": _fmt(o.updated_at),
        "prescription": rx_out,
    }


# —— 提现审批（§4.3）——
@router.get("/withdrawals")
async def list_withdrawals(user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    ws = await finance_service.list_withdrawals(db)
    return [
        {"id": w.id, "doctor": w.doctor_name, "amount": w.amount_fen / 100,
         "status": w.status, "created_at": _fmt(w.created_at)}
        for w in ws
    ]


@router.post("/withdrawals/{wid}/audit")
async def audit_withdrawal(wid: int, request: Request, approve: bool = Body(embed=True), user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    try:
        # 通过 → paid（演示：此处应调微信「商家转账到零钱」后再置 paid）
        w = await finance_service.set_withdrawal_status(db, wid, "paid" if approve else "rejected")
        await audit_service.record(
            db, user, request, "提现" + ("打款" if approve else "驳回"),
            "withdrawal", wid, f"{w.doctor_name} ¥{w.amount_fen / 100}",
        )
        await db.commit()
    except finance_service.FinanceError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    return {"id": w.id, "status": w.status}


# —— 监管上报监控面板（§4.4 / M9）——
@router.get("/gov-reports/stats")
async def gov_report_stats(user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    return await compliance_service.stats(db)


@router.get("/gov-reports/failed")
async def gov_report_failed(user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    items = await compliance_service.list_failed(db)
    return [
        {"id": r.id, "type": r.biz_type, "biz_id": r.biz_id, "status": r.status,
         "retries": r.retries, "err": r.last_error}
        for r in items
    ]


@router.post("/gov-reports/{rid}/retry")
async def gov_report_retry(rid: int, user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    r = await compliance_service.retry(db, rid)
    if not r:
        raise HTTPException(status_code=404, detail="上报任务不存在")
    return {"id": r.id, "status": r.status}


# —— 运营数据大盘 ——
@router.get("/overview")
async def overview(user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    async def _count(model, *where):
        q = select(func.count()).select_from(model)
        for w in where:
            q = q.where(w)
        return int(await db.scalar(q) or 0)

    total_orders = await _count(Order)
    today_orders = await _count(Order, Order.created_at >= today)
    paid_orders = await _count(Order, Order.status.notin_([0, 9]))
    pending_rx = await _count(Prescription, Prescription.audit_status == "pending")
    doctors_total = await _count(Doctor)
    doctors_approved = await _count(Doctor, Doctor.audit_status == "approved")
    doctors_pending = await _count(Doctor, Doctor.audit_status == "pending")
    patients = await _count(Patient)
    pending_withdrawals = await _count(Withdrawal, Withdrawal.status == "pending")

    revenue_total = int(await db.scalar(select(func.coalesce(func.sum(Ledger.total_fen), 0))) or 0)
    today_revenue = int(await db.scalar(
        select(func.coalesce(func.sum(Ledger.total_fen), 0)).where(Ledger.created_at >= today)
    ) or 0)
    balance = await finance_service.doctor_balance_fen(db)

    # 订单状态分布
    rows = await db.execute(select(Order.status, func.count()).group_by(Order.status))
    dist = [{"status": s, "status_text": ORDER_STATUS_TEXT.get(s, str(s)), "count": int(c)} for s, c in rows.all()]

    return {
        "total_orders": total_orders, "today_orders": today_orders, "paid_orders": paid_orders,
        "revenue_total": revenue_total / 100, "today_revenue": today_revenue / 100,
        "doctor_balance": balance / 100,
        "doctors_total": doctors_total, "doctors_approved": doctors_approved, "doctors_pending": doctors_pending,
        "patients": patients, "pending_rx": pending_rx, "pending_withdrawals": pending_withdrawals,
        "status_dist": dist,
    }


# —— 操作审计日志 ——
@router.get("/audit-logs")
async def audit_logs(action: str | None = None, actor: str | None = None, user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    items = await audit_service.query(db, action=action, actor=actor)
    return [
        {"id": a.id, "actor_name": a.actor_name, "actor_role": a.actor_role, "action": a.action,
         "target_type": a.target_type, "target_id": a.target_id, "detail": a.detail,
         "ip": a.ip, "created_at": _fmt(a.created_at)}
        for a in items
    ]


# —— 运营账号管理（RBAC）——
@router.get("/staff")
async def list_staff(user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    return [
        {"id": s.id, "username": s.username, "name": s.name, "role": s.role,
         "active": s.active, "created_at": _fmt(s.created_at)}
        for s in await staff_service.list_staff(db)
    ]


@router.post("/staff")
async def create_staff(request: Request, body: dict = Body(...), user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    try:
        s = await staff_service.create_staff(
            db, body.get("username", "").strip(), body.get("password", ""),
            body.get("role", "pharmacist"), body.get("name"),
        )
        await audit_service.record(db, user, request, "创建账号", "staff", s.id, f"{s.username}({s.role})")
        await db.commit()
    except staff_service.StaffError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    return {"id": s.id}


@router.put("/staff/{staff_id}")
async def update_staff(staff_id: int, request: Request, body: dict = Body(...), user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    # 禁止停用/降级最后一个在用 admin，避免锁死后台
    if staff_id == int(user["sub"]) and (body.get("active") is False or (body.get("role") and body["role"] != "admin")):
        raise HTTPException(status_code=409, detail="不能停用或降级当前登录的自己")
    try:
        s = await staff_service.update_staff(
            db, staff_id, name=body.get("name"), role=body.get("role"), active=body.get("active"),
        )
        await audit_service.record(db, user, request, "编辑账号", "staff", staff_id, f"{s.username}({s.role},{'启用' if s.active else '停用'})")
        await db.commit()
    except staff_service.StaffError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    return {"id": s.id}


@router.post("/staff/{staff_id}/reset-password")
async def reset_staff_password(staff_id: int, request: Request, body: dict = Body(...), user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    try:
        s = await staff_service.reset_password(db, staff_id, body.get("password", ""))
        await audit_service.record(db, user, request, "重置密码", "staff", staff_id, s.username)
        await db.commit()
    except staff_service.StaffError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    return {"ok": True}


@router.delete("/staff/{staff_id}")
async def delete_staff(staff_id: int, request: Request, user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    if staff_id == int(user["sub"]):
        raise HTTPException(status_code=409, detail="不能删除当前登录的自己")
    target = await db.get(Staff, staff_id)
    if target and target.role == "admin" and await staff_service.count_active_admins(db) <= 1:
        raise HTTPException(status_code=409, detail="不能删除最后一个管理员")
    try:
        await staff_service.delete_staff(db, staff_id)
        await audit_service.record(db, user, request, "删除账号", "staff", staff_id, target.username if target else str(staff_id))
        await db.commit()
    except staff_service.StaffError as e:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}
