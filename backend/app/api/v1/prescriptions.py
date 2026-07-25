"""处方接口（M5）：医生开方 / 药师审方 / 患者查看。"""
import hashlib
import io

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import select

from ...core.security import mask_name
from ...core.database import get_db
from ...core.config import settings
from ...models.order import Order
from ...models.prescription import Prescription
from ...models.staff import Staff
from ...models.user import Doctor, Patient
from ...schemas.prescription import PrescriptionCreate, PrescriptionOut, RejectIn
from ...services import audit_service, compliance_service
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
async def approve(rx_id: int, request: Request, user=Depends(require_role("pharmacist", "admin")), db: AsyncSession = Depends(get_db)):
    try:
        # 监管上报改为审方通过后 T+1 每日批量采集（tj_collector）；此处记录审方药师
        rx = await rx_service.approve(db, rx_id, staff_id=int(user["sub"]))
        await audit_service.record(db, user, request, "审方通过", "prescription", rx_id, f"订单{rx.order_id}")
        await db.commit()
    except rx_service.RxError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    return await _decorate(db, rx)


@router.post("/{rx_id}/reject", response_model=PrescriptionOut)
async def reject(rx_id: int, body: RejectIn, request: Request, user=Depends(require_role("pharmacist", "admin")), db: AsyncSession = Depends(get_db)):
    try:
        rx = await rx_service.reject(db, rx_id, body.reason)
        await audit_service.record(db, user, request, "审方驳回", "prescription", rx_id, body.reason)
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
    """处方 PDF；生产要求 CA 时，未签名文件禁止下载。"""
    rx = await rx_service.get_by_order(db, order_id)
    if not rx:
        raise HTTPException(status_code=404, detail="暂无处方")
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    role, uid = user.get("role"), int(user["sub"])
    allowed = role in {"pharmacist", "admin"}
    if role == "patient":
        allowed = order.user_id == uid
    elif role == "doctor":
        res = await db.execute(select(Doctor).where(Doctor.user_id == uid))
        doctor_user = res.scalar_one_or_none()
        allowed = bool(doctor_user and doctor_user.id == order.doctor_id)
    if not allowed:
        raise HTTPException(status_code=403, detail="无权查看该处方")

    if rx.ca_sign_status == "verified" and rx.pdf_url:
        from ...services import fxq_document_service

        try:
            data = fxq_document_service.load_signed_pdf(rx.pdf_url)
        except fxq_document_service.FxqDocumentError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if rx.ca_file_digest and hashlib.sha256(data).hexdigest() != rx.ca_file_digest:
            raise HTTPException(status_code=503, detail="签后 PDF 归档摘要校验失败，已拒绝下载")
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="prescription-{order_id}-signed.pdf"'},
        )

    if settings.FXQ_CA_REQUIRED or (
        settings.FXQ_DOCUMENT_SIGN_ENABLED and rx.audit_status == "approved"
    ):
        raise HTTPException(status_code=409, detail="处方尚未完成文档数字签名，不能作为有效处方下载")
    doctor = await db.get(Doctor, rx.doctor_id)
    patient = await db.get(Patient, rx.patient_id)
    pharmacist = await db.get(Staff, rx.audit_staff_id) if rx.audit_staff_id else None
    data = compliance_service.generate_prescription_pdf(
        rx,
        patient.name if patient else "患者",
        doctor.name if doctor else "医生",
        pharmacist.name if pharmacist else None,
    )
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="prescription-{order_id}-preview.pdf"'},
    )
