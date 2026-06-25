"""处方接口（M5）：医生开方 / 药师审方 / 患者查看。"""
import io

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from ...core.security import mask_name
from ...core.database import get_db
from ...models.order import Order
from ...models.prescription import Prescription
from ...models.user import Doctor, Patient
from ...schemas.prescription import PrescriptionCreate, PrescriptionOut, RejectIn
from ...services import compliance_service
from ...services import prescription_service as rx_service
from ..deps import get_current_user, get_current_user_id, require_approved_doctor, require_role

router = APIRouter(prefix="/prescriptions", tags=["prescriptions"])


async def _decorate(db: AsyncSession, rx) -> PrescriptionOut:
    out = PrescriptionOut.model_validate(rx)
    doctor = await db.get(Doctor, rx.doctor_id)
    patient = await db.get(Patient, rx.patient_id)
    out.doctor_name = doctor.name if doctor else None
    out.patient_name = mask_name(patient.name) if patient else None
    return out


@router.post("", response_model=PrescriptionOut)
async def submit(body: PrescriptionCreate, user=Depends(require_approved_doctor), db: AsyncSession = Depends(get_db)):
    try:
        rx = await rx_service.submit(db, int(user["sub"]), body)
        await db.commit()
    except rx_service.RxError as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    return await _decorate(db, rx)


@router.get("/pending", response_model=list[PrescriptionOut])
async def pending(user=Depends(require_role("pharmacist", "admin")), db: AsyncSession = Depends(get_db)):
    rxs = await rx_service.list_pending(db)
    return [await _decorate(db, r) for r in rxs]


@router.post("/{rx_id}/approve", response_model=PrescriptionOut)
async def approve(rx_id: int, user=Depends(require_role("pharmacist", "admin")), db: AsyncSession = Depends(get_db)):
    try:
        rx = await rx_service.approve(db, rx_id)
        await compliance_service.enqueue(db, "prescription", rx.order_id)  # 开药明细上报卫健委
        await db.commit()
    except rx_service.RxError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    return await _decorate(db, rx)


@router.post("/{rx_id}/reject", response_model=PrescriptionOut)
async def reject(rx_id: int, body: RejectIn, user=Depends(require_role("pharmacist", "admin")), db: AsyncSession = Depends(get_db)):
    try:
        rx = await rx_service.reject(db, rx_id, body.reason)
        await db.commit()
    except rx_service.RxError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    return await _decorate(db, rx)


@router.get("/mine", response_model=list[PrescriptionOut])
async def my_prescriptions(uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """患者本人处方列表（我的处方）。"""
    res = await db.execute(
        select(Prescription)
        .join(Order, Order.id == Prescription.order_id)
        .where(Order.user_id == uid)
        .order_by(Prescription.id.desc())
    )
    return [await _decorate(db, rx) for rx in res.scalars().all()]


@router.get("/by-order/{order_id}", response_model=PrescriptionOut)
async def by_order(order_id: int, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rx = await rx_service.get_by_order(db, order_id)
    if not rx:
        raise HTTPException(status_code=404, detail="暂无处方")
    return await _decorate(db, rx)


@router.get("/{order_id}/pdf")
async def pdf(order_id: int, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """处方 PDF（reportlab 生成，红章占位）。"""
    rx = await rx_service.get_by_order(db, order_id)
    if not rx:
        raise HTTPException(status_code=404, detail="暂无处方")
    doctor = await db.get(Doctor, rx.doctor_id)
    patient = await db.get(Patient, rx.patient_id)
    data = compliance_service.generate_prescription_pdf(
        rx, patient.name if patient else "患者", doctor.name if doctor else "医生"
    )
    return StreamingResponse(io.BytesIO(data), media_type="application/pdf")
