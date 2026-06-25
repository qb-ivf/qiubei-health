"""运营总管理后台接口（PRD 子系统3，M8）。需 admin 角色。"""
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.crypto import decrypt
from ...core.database import get_db
from ...core.security import mask_name, mask_phone
from ...models.drug import Drug
from ...models.order import Order
from ...models.prescription import Prescription
from ...models.user import Doctor, Patient, User
from ...services import compliance_service, finance_service
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
async def audit_doctor(doctor_id: int, approve: bool = Body(embed=True), user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    d = await db.get(Doctor, doctor_id)
    if not d:
        raise HTTPException(status_code=404, detail="医生不存在")
    d.audit_status = "approved" if approve else "rejected"
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
async def add_drug(body: dict = Body(...), user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    drug = Drug(
        name=body["name"], spec=body.get("spec"),
        price_fen=int(round(float(body.get("price", 0)) * 100)),
        category=body.get("category", "处方药"),
        restricted=bool(body.get("restricted", False)),
    )
    db.add(drug)
    await db.commit()
    return {"id": drug.id}


@router.put("/drugs/{drug_id}")
async def update_drug(drug_id: int, body: dict = Body(...), user=Depends(_admin), db: AsyncSession = Depends(get_db)):
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
    await db.commit()
    return {"id": drug.id}


@router.delete("/drugs/{drug_id}")
async def delete_drug(drug_id: int, user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    drug = await db.get(Drug, drug_id)
    if not drug:
        raise HTTPException(status_code=404, detail="药品不存在")
    await db.delete(drug)
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
            "diagnosis": rx.diagnosis, "items": rx.items or [],
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
async def audit_withdrawal(wid: int, approve: bool = Body(embed=True), user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    try:
        # 通过 → paid（演示：此处应调微信「商家转账到零钱」后再置 paid）
        w = await finance_service.set_withdrawal_status(db, wid, "paid" if approve else "rejected")
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
