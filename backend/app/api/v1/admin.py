"""运营总管理后台接口（PRD 子系统3，M8）。需 admin 角色。"""
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...constants import OrderStatus
from ...core.crypto import decrypt
from ...core.database import get_db
from ...core.security import mask_name, mask_phone
from ...models.drug import Drug
from ...models.evaluation import Evaluation
from ...models.medical_dispute import MedicalDispute
from ...models.order import Order
from ...models.prescription import Prescription
from ...models.staff import Staff
from ...models.user import Doctor, Patient, User
from ...models.withdrawal import Withdrawal
from ...schemas.doctor import SlotQuotaIn, SlotsCreate
from ...services import (
    audit_service, compliance_service, demographics, doctor_service, finance_service,
    staff_service, tj_collector, tj_mappers,
)
from ..deps import require_role

router = APIRouter(prefix="/admin", tags=["admin"])
_admin = require_role("admin")

# 订单状态文案（与 constants.OrderStatus 对齐）
ORDER_STATUS_TEXT = {
    0: "待支付", 1: "候诊中", 2: "问诊中", 3: "待审方",
    4: "审方驳回", 5: "已开方", 6: "已完成", 7: "已退款", 9: "已取消",
}


# 数据库统一存 naive UTC；运营后台展示与「今日/月份」边界均按北京时间。
# 中国全境固定 UTC+8（无夏令时），用固定偏移避免依赖系统 tzdata。
CN_TZ = timezone(timedelta(hours=8))


def _fmt(dt) -> str:
    """naive UTC → 北京时间字符串。"""
    if not dt:
        return ""
    return dt.replace(tzinfo=timezone.utc).astimezone(CN_TZ).strftime("%Y-%m-%d %H:%M")


def _cn_midnight_utc(d: date) -> datetime:
    """某个北京日期的 00:00，转成 naive UTC（用于和库里 UTC 时间比较）。"""
    return datetime(d.year, d.month, d.day, tzinfo=CN_TZ).astimezone(timezone.utc).replace(tzinfo=None)


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


# —— 医生排班管理（运营代医生开号/加减号/删号，复用医生端 Redis 同步逻辑）——
@router.get("/no-slot-doctors")
async def no_slot_doctors(user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    """侧边栏角标用：无可约号源的在册医生计数 + 名单（轻量，避开整个 overview）。"""
    items = await doctor_service.doctors_lacking_slots(db)
    return {"count": len(items), "list": items}


@router.get("/doctors/{doctor_id}/schedule")
async def doctor_schedule(doctor_id: int, day: str | None = None, user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    return await doctor_service.get_schedule(db, doctor_id, day)


@router.post("/doctors/{doctor_id}/slots")
async def admin_create_slots(doctor_id: int, request: Request, body: SlotsCreate, user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    d = await db.get(Doctor, doctor_id)
    if not d:
        raise HTTPException(status_code=404, detail="医生不存在")
    out = await doctor_service.create_slots(db, doctor_id, body.day, body.times, body.quota)
    await audit_service.record(
        db, user, request, "代开号源", "doctor", doctor_id,
        f"{d.name or doctor_id} {body.day} ×{len(out)}个时段/各{max(1, body.quota)}号",
    )
    await db.commit()
    return out


@router.patch("/slots/{slot_id}")
async def admin_update_slot(slot_id: int, request: Request, body: SlotQuotaIn, user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    try:
        slot = await doctor_service.set_slot_quota(db, slot_id, body.quota)
    except doctor_service.ScheduleError as e:
        raise HTTPException(status_code=409, detail=str(e))
    await audit_service.record(db, user, request, "调整号源", "slot", slot_id, f"{slot.day} {slot.start_time} → {slot.quota}号")
    await db.commit()
    return slot


@router.delete("/slots/{slot_id}")
async def admin_delete_slot(slot_id: int, request: Request, user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    try:
        slot = await doctor_service.delete_slot(db, slot_id)
    except doctor_service.ScheduleError as e:
        raise HTTPException(status_code=409, detail=str(e))
    await audit_service.record(db, user, request, "删除号源", "slot", slot_id, f"{slot.day} {slot.start_time}")
    await db.commit()
    return {"ok": True}


@router.put("/doctors/{doctor_id}")
async def update_doctor(doctor_id: int, request: Request, body: dict = Body(...), user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    """运营编辑医生信息（资料填错/代填修正）。挂号费单位为元，转存分。"""
    d = await db.get(Doctor, doctor_id)
    if not d:
        raise HTTPException(status_code=404, detail="医生不存在")
    if "name" in body:
        d.name = (body["name"] or "").strip() or None
    if "dept" in body:
        d.dept = (body.get("dept") or "").strip() or None
    if "title" in body:
        d.title = (body.get("title") or "").strip() or None
    if "license_no" in body:
        d.license_no = (body.get("license_no") or "").strip() or None
    if "practice_no" in body:
        d.practice_no = (body.get("practice_no") or "").strip() or None
    if "good_at" in body:
        d.good_at = (body.get("good_at") or "").strip() or None
    if "years" in body:
        d.years = int(body["years"]) if body.get("years") not in (None, "") else None
    if "register_fee" in body:
        fee = float(body["register_fee"] or 0)
        if fee < 0:
            raise HTTPException(status_code=400, detail="挂号费不能为负")
        d.register_fee_fen = int(round(fee * 100))
    await audit_service.record(db, user, request, "编辑医生信息", "doctor", doctor_id, d.name or str(doctor_id))
    await db.commit()
    return {"id": d.id}


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


# —— 药品字典（§4.2；增改删触发监管药品目录即时上报 2.1.1）——
async def _enqueue_drug_catalogue(db, drug, use_flag: str | None = None):
    await compliance_service.enqueue(
        db, "drug", drug.id, "uploadDrugCatalogue",
        [tj_mappers.build_drug(drug, use_flag)], refresh=True,
    )


@router.get("/drugs")
async def list_drugs(user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Drug).order_by(Drug.id.asc()))
    return [
        {"id": x.id, "name": x.name, "spec": x.spec, "price": x.price_fen / 100,
         "category": x.category, "restricted": x.restricted,
         "drug_class": x.drug_class, "countrydrcode": x.countrydrcode,
         "packing": x.packing, "manufacturer": x.manufacturer}
        for x in res.scalars().all()
    ]


_DRUG_TJ_FIELDS = ("drug_class", "countrydrcode", "packing", "manufacturer")


@router.post("/drugs")
async def add_drug(request: Request, body: dict = Body(...), user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    drug = Drug(
        name=body["name"], spec=body.get("spec"),
        price_fen=int(round(float(body.get("price", 0)) * 100)),
        category=body.get("category", "处方药"),
        restricted=bool(body.get("restricted", False)),
        **{f: body.get(f) for f in _DRUG_TJ_FIELDS},
    )
    db.add(drug)
    await db.flush()
    await _enqueue_drug_catalogue(db, drug)
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
    for f in _DRUG_TJ_FIELDS:
        if f in body:
            setattr(drug, f, body.get(f))
    await _enqueue_drug_catalogue(db, drug)
    await audit_service.record(db, user, request, "编辑药品", "drug", drug_id, drug.name)
    await db.commit()
    return {"id": drug.id}


@router.delete("/drugs/{drug_id}")
async def delete_drug(drug_id: int, request: Request, user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    drug = await db.get(Drug, drug_id)
    if not drug:
        raise HTTPException(status_code=404, detail="药品不存在")
    name = drug.name
    await _enqueue_drug_catalogue(db, drug, use_flag="2")  # 监管目录置为「取消」
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
         "method": r.method, "batch_date": str(r.batch_date) if r.batch_date else None,
         "msg_code": r.msg_code, "retries": r.retries,
         "err": r.last_error or r.resp_msg, "payload": r.payload}
        for r in items
    ]


@router.post("/gov-reports/{rid}/retry")
async def gov_report_retry(rid: int, user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    r = await compliance_service.retry(db, rid)
    if not r:
        raise HTTPException(status_code=404, detail="上报任务不存在")
    return {"id": r.id, "status": r.status}


@router.post("/gov-reports/collect")
async def gov_report_collect(request: Request, body: dict = Body(...), user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    """手工按日补采（S4）：body={"day":"YYYY-MM-DD"}（北京时间日期）。幂等，可重复执行。"""
    try:
        day = date.fromisoformat(str(body.get("day", "")))
    except ValueError:
        raise HTTPException(status_code=422, detail="day 格式应为 YYYY-MM-DD")
    counts = await tj_collector.collect_daily(db, day)
    await audit_service.record(db, user, request, "手工补采监管数据", "gov_report", 0, str(day))
    await db.commit()
    return {"day": str(day), "counts": counts}


# —— 患者评价（监管 2.4.1 数据源，只读） ——
@router.get("/evaluations")
async def list_evaluations(user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Evaluation).order_by(Evaluation.id.desc()).limit(500))
    out = []
    for ev in res.scalars().all():
        order = await db.get(Order, ev.order_id)
        doctor = await db.get(Doctor, ev.doctor_id)
        out.append({
            "id": ev.id, "order_no": order.order_no if order else None,
            "consult_type": order.consult_type if order else None,
            "doctor_name": doctor.name if doctor else None,
            "satisfaction": ev.satisfaction, "scoring": ev.scoring,
            "content": ev.content, "complaints": ev.complaints,
            "evaluator": mask_name(ev.evaluator) if ev.evaluator else None,
            "created_at": _fmt(ev.created_at),
        })
    return out


# —— 医疗争议 / 不良事件登记（监管 2.4.2 每日签到数据源；合规记录不提供删除） ——
_DISPUTE_FIELDS = (
    "business_type", "patient_name", "mobile", "event_description", "event_reason",
    "take_steps", "damage_degree", "improvements", "report_dept", "report_person",
)


@router.get("/disputes")
async def list_disputes(user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(MedicalDispute).order_by(MedicalDispute.id.desc()).limit(500))
    return [
        {
            "id": d.id, "order_id": d.order_id, "business_type": d.business_type,
            "patient_name": d.patient_name, "mobile": d.mobile,
            "event_description": d.event_description,
            "event_date": _fmt(d.event_date), "event_reason": d.event_reason,
            "take_steps": d.take_steps, "damage_degree": d.damage_degree,
            "improvements": d.improvements, "report_dept": d.report_dept,
            "report_person": d.report_person, "report_date": _fmt(d.report_date),
        }
        for d in res.scalars().all()
    ]


def _parse_cn_datetime(s: str) -> datetime:
    """北京时间字符串 → naive UTC（与库内时间基准一致）。"""
    dt = datetime.strptime(s, "%Y-%m-%d %H:%M")
    return dt.replace(tzinfo=CN_TZ).astimezone(timezone.utc).replace(tzinfo=None)


@router.post("/disputes")
async def create_dispute(request: Request, body: dict = Body(...), user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    missing = [f for f in _DISPUTE_FIELDS if not str(body.get(f, "")).strip()]
    if missing or not body.get("event_date"):
        raise HTTPException(status_code=422, detail="必填项不完整")
    try:
        event_date = _parse_cn_datetime(body["event_date"])
    except ValueError:
        raise HTTPException(status_code=422, detail="事件发生时间格式应为 YYYY-MM-DD HH:MM")
    d = MedicalDispute(
        order_id=body.get("order_id"),
        event_date=event_date,
        report_date=datetime.now(timezone.utc).replace(tzinfo=None),
        **{f: str(body[f]).strip() for f in _DISPUTE_FIELDS},
    )
    db.add(d)
    await db.flush()
    await audit_service.record(db, user, request, "登记不良事件", "dispute", d.id, d.event_description[:50])
    await db.commit()
    return {"id": d.id}


@router.put("/disputes/{did}")
async def update_dispute(did: int, request: Request, body: dict = Body(...), user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    d = await db.get(MedicalDispute, did)
    if not d:
        raise HTTPException(status_code=404, detail="记录不存在")
    for f in _DISPUTE_FIELDS:
        if body.get(f) is not None:
            setattr(d, f, str(body[f]).strip())
    if body.get("event_date"):
        try:
            d.event_date = _parse_cn_datetime(body["event_date"])
        except ValueError:
            raise HTTPException(status_code=422, detail="事件发生时间格式应为 YYYY-MM-DD HH:MM")
    await audit_service.record(db, user, request, "修改不良事件", "dispute", did, "")
    await db.commit()
    return {"id": d.id}


# —— 运营数据大盘 ——
@router.get("/overview")
async def overview(user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    now_cn = datetime.now(CN_TZ)
    today = _cn_midnight_utc(now_cn.date())  # 今日(北京) 0 点，UTC 表示

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

    async def _sum(col, *where):
        q = select(func.coalesce(func.sum(col), 0))
        for w in where:
            q = q.where(w)
        return int(await db.scalar(q) or 0)

    # 成交额(GMV)=已支付订单的挂号费 + 已完成订单实付药费。
    # 注：与分账 Ledger 口径不同——挂号费支付即计入成交额，药费仅在已完成(已付)时计入。
    paid = Order.status.notin_([int(OrderStatus.PENDING), int(OrderStatus.CANCELLED), int(OrderStatus.REFUNDED)])
    finished = Order.status == int(OrderStatus.FINISHED)
    revenue_total = await _sum(Order.register_fee_fen, paid) + await _sum(Order.drug_fee_fen, finished)
    today_revenue = (await _sum(Order.register_fee_fen, paid, Order.created_at >= today)
                     + await _sum(Order.drug_fee_fen, finished, Order.created_at >= today))
    balance = await finance_service.doctor_balance_fen(db)

    # 订单状态分布
    rows = await db.execute(select(Order.status, func.count()).group_by(Order.status))
    dist = [{"status": s, "status_text": ORDER_STATUS_TEXT.get(s, str(s)), "count": int(c)} for s, c in rows.all()]

    # 今日新增就诊人 / 昨日新增（算环比）/ 正在问诊（候诊中+问诊中）
    yesterday = _cn_midnight_utc(now_cn.date() - timedelta(days=1))
    today_new_patients = await _count(Patient, Patient.created_at >= today)
    yest_new_patients = await _count(Patient, Patient.created_at >= yesterday, Patient.created_at < today)
    in_treatment = await _count(Order, Order.status.in_([OrderStatus.WAITING, OrderStatus.CONSULTING]))

    # 就诊人增长趋势（近 12 个月，按北京时间月份计数）
    y, m = now_cn.year, now_cn.month
    ym = []
    for _ in range(12):
        ym.append((y, m))
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    ym.reverse()
    months = []
    for (yy, mm) in ym:
        start = _cn_midnight_utc(date(yy, mm, 1))
        nyy, nmm = (yy + 1, 1) if mm == 12 else (yy, mm + 1)
        end = _cn_midnight_utc(date(nyy, nmm, 1))
        cnt = await _count(Patient, Patient.created_at >= start, Patient.created_at < end)
        months.append({"month": f"{yy:04d}-{mm:02d}", "count": cnt})

    # 全国患者分布 + 年龄分布（解析身份证：前2位省级码、7-14位出生日期）
    today_d = now_cn.date()
    geo: dict[str, int] = {}
    age_counts = {label: 0 for label, _, _ in demographics.AGE_BUCKETS}
    id_rows = await db.execute(select(Patient.id_card_enc).where(Patient.id_card_enc.isnot(None)))
    for (enc,) in id_rows.all():
        info = demographics.parse_id_card(_safe_decrypt(enc), today_d)
        if not info:
            continue
        if info["province"]:
            geo[info["province"]] = geo.get(info["province"], 0) + 1
        if info["age"] is not None:
            bucket = demographics.age_bucket(info["age"])
            if bucket:
                age_counts[bucket] += 1
    patient_geo = [{"province": p, "count": c} for p, c in sorted(geo.items(), key=lambda x: -x[1])]
    age_dist = [{"label": label, "count": age_counts[label]} for label, _, _ in demographics.AGE_BUCKETS]

    # 在册医生但无可约号源（患者约不上号）
    no_slot_doctors = await doctor_service.doctors_lacking_slots(db)

    # 系统动态消息：最近运营操作（复用审计日志）
    recent_activity = [
        {"id": a.id, "actor_name": a.actor_name or "系统", "actor_role": a.actor_role,
         "action": a.action, "target_type": a.target_type, "detail": a.detail,
         "created_at": _fmt(a.created_at)}
        for a in await audit_service.query(db, limit=12)
    ]

    return {
        "total_orders": total_orders, "today_orders": today_orders, "paid_orders": paid_orders,
        "revenue_total": revenue_total / 100, "today_revenue": today_revenue / 100,
        "doctor_balance": balance / 100,
        "doctors_total": doctors_total, "doctors_approved": doctors_approved, "doctors_pending": doctors_pending,
        "patients": patients, "pending_rx": pending_rx, "pending_withdrawals": pending_withdrawals,
        "today_new_patients": today_new_patients, "yest_new_patients": yest_new_patients,
        "in_treatment": in_treatment,
        "status_dist": dist,
        "growth_trend": months, "patient_geo": patient_geo, "age_dist": age_dist,
        "doctors_no_slots": len(no_slot_doctors), "doctors_no_slots_list": no_slot_doctors,
        "recent_activity": recent_activity,
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
