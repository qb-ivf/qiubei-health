"""运营总管理后台接口（PRD 子系统3，M8）。需 admin 角色。"""
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...core.security import mask_id_card
from ...models.drug import Drug
from ...models.user import Doctor
from ...services import compliance_service, finance_service
from ..deps import require_role

router = APIRouter(prefix="/admin", tags=["admin"])
_admin = require_role("admin")


# —— 医生资质终审（§4.1）——
@router.get("/doctors")
async def list_doctors(user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Doctor).order_by(Doctor.id.asc()))
    return [
        {
            "id": d.id, "name": d.name, "dept": d.dept, "title": d.title,
            "license_no": d.license_no, "practice_no": d.practice_no,
            "audit_status": d.audit_status,
        }
        for d in res.scalars().all()
    ]


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


# —— 提现审批（§4.3）——
@router.get("/withdrawals")
async def list_withdrawals(user=Depends(_admin), db: AsyncSession = Depends(get_db)):
    ws = await finance_service.list_withdrawals(db)
    return [{"id": w.id, "doctor": w.doctor_name, "amount": w.amount_fen / 100, "status": w.status} for w in ws]


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
