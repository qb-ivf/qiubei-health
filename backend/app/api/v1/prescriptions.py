"""处方接口（M5）：医生开方 / 药师审方 / 患者查看。"""
import hashlib
import io
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import or_, select

from ...core.security import mask_name
from ...core.database import get_db
from ...core.config import settings
from ...constants import Signal
from ...models.order import Order
from ...models.prescription import Prescription
from ...models.staff import Staff
from ...models.user import Doctor, Patient
from ...schemas.prescription import PrescriptionCreate, PrescriptionOut, RejectIn
from ...services import audit_service, compliance_service
from ...services import prescription_service as rx_service
from ...ws import manager
from ..deps import get_current_user, require_approved_doctor, require_role

router = APIRouter(prefix="/prescriptions", tags=["prescriptions"])
logger = logging.getLogger(__name__)


async def _decorate(db: AsyncSession, rx) -> PrescriptionOut:
    out = PrescriptionOut.model_validate(rx)
    doctor = await db.get(Doctor, rx.doctor_id)
    patient = await db.get(Patient, rx.patient_id)
    out.doctor_name = doctor.name if doctor else None
    out.patient_name = mask_name(patient.name) if patient else None
    return out


async def _medical_record_out(db: AsyncSession, rx: Prescription) -> dict:
    doctor = await db.get(Doctor, rx.doctor_id)
    return {
        "id": rx.id,
        "order_id": rx.order_id,
        "doctor_name": doctor.name if doctor else None,
        "dept": doctor.dept if doctor else None,
        "chief": rx.chief,
        "present_illness": rx.present_illness,
        "diagnosis": rx.diagnosis,
        "icd_code": rx.icd_code,
        "icd_name": rx.icd_name,
        "advice": rx.advice,
        "has_prescription": bool(rx.audit_status != "not_required" and rx.items),
        "signed": rx.ca_sign_status == "verified",
        "created_at": rx.created_at,
        "updated_at": rx.updated_at,
    }


async def _can_view_order_record(db: AsyncSession, user: dict, order: Order) -> bool:
    role, uid = user.get("role"), int(user["sub"])
    if role == "patient":
        return order.user_id == uid
    if role == "doctor":
        res = await db.execute(select(Doctor).where(Doctor.user_id == uid))
        doctor = res.scalar_one_or_none()
        return bool(doctor and doctor.id == order.doctor_id)
    return role in {"pharmacist", "admin"}


@router.post("", response_model=PrescriptionOut)
async def submit(body: PrescriptionCreate, user=Depends(require_approved_doctor), db: AsyncSession = Depends(get_db)):
    try:
        rx = await rx_service.submit(db, int(user["sub"]), body)
        await db.commit()
    except rx_service.RxError as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    order = await db.get(Order, rx.order_id)
    if order:
        await manager.send(
            order.user_id,
            {
                "type": Signal.CALL_FINISHED,
                "roomId": order.room_id,
                "result": "prescription",
                "orderId": order.id,
            },
        )
        if order.room_id:
            await manager.delete_room(order.room_id)
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
        detail = str(e)
        if e.manual_review:
            try:
                await rx_service.mark_signing_manual_review(db, rx_id)
                code = f"，供应商代码 {e.provider_code}" if e.provider_code else ""
                await audit_service.record(
                    db,
                    user,
                    request,
                    "CA签署待确认",
                    "prescription",
                    rx_id,
                    f"供应商响应不确定{code}；已禁止重复签署",
                )
                await db.commit()
                detail += "；供应商结果待人工确认，系统已禁止重复签署"
            except Exception:  # noqa: BLE001
                await db.rollback()
                logger.exception("处方 %s 的 CA 人工复核锁定保存失败", rx_id)
                detail += "；人工复核锁定保存失败，请勿重试并立即联系技术人员"
        raise HTTPException(status_code=409, detail=detail)
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
async def my_prescriptions(
    user=Depends(require_role("patient")),
    db: AsyncSession = Depends(get_db),
):
    """患者本人处方列表（我的处方）。"""
    uid = int(user["sub"])
    res = await db.execute(
        select(Prescription)
        .join(Order, Order.id == Prescription.order_id)
        .where(
            Order.user_id == uid,
            Prescription.audit_status != "not_required",
        )
        .order_by(Prescription.id.desc())
    )
    return [await _decorate(db, rx) for rx in res.scalars().all()]


@router.get("/records/mine")
async def my_medical_records(
    user=Depends(require_role("patient")),
    db: AsyncSession = Depends(get_db),
):
    """患者本人的电子病历列表；包含有处方和无处方两类问诊。"""
    uid = int(user["sub"])
    res = await db.execute(
        select(Prescription)
        .join(Order, Order.id == Prescription.order_id)
        .where(
            Order.user_id == uid,
            or_(
                Prescription.ca_sign_status.is_(None),
                Prescription.ca_sign_status != "manual_review",
            ),
        )
        .order_by(Prescription.id.desc())
    )
    return [await _medical_record_out(db, rx) for rx in res.scalars().all()]


@router.get("/record/by-order/{order_id}")
async def medical_record_by_order(
    order_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rx = await rx_service.get_by_order(db, order_id)
    order = await db.get(Order, order_id)
    if not rx or not order:
        raise HTTPException(status_code=404, detail="暂无电子病历")
    if not await _can_view_order_record(db, user, order):
        raise HTTPException(status_code=403, detail="无权查看该电子病历")
    if rx.ca_sign_status == "manual_review":
        raise HTTPException(status_code=409, detail="电子病历签署结果待人工确认，暂不可查看")
    return await _medical_record_out(db, rx)


@router.get("/record/{order_id}/pdf")
async def medical_record_pdf(
    order_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """无药问诊电子病历 PDF；生产 CA 模式只允许下载医师+医院两方验签原件。"""
    rx = await rx_service.get_by_order(db, order_id)
    order = await db.get(Order, order_id)
    if not rx or not order or rx.audit_status != "not_required":
        raise HTTPException(status_code=404, detail="本次问诊没有独立的无药电子病历 PDF")
    if not await _can_view_order_record(db, user, order):
        raise HTTPException(status_code=403, detail="无权查看该电子病历")

    if rx.ca_sign_status == "verified" and rx.pdf_url:
        from ...services import fxq_document_service

        try:
            data = fxq_document_service.load_signed_pdf(rx.pdf_url)
        except fxq_document_service.FxqDocumentError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if rx.ca_file_digest and hashlib.sha256(data).hexdigest() != rx.ca_file_digest:
            raise HTTPException(status_code=503, detail="签后电子病历归档摘要校验失败，已拒绝下载")
        return StreamingResponse(
            io.BytesIO(data),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="medical-record-{order_id}-signed.pdf"'
            },
        )

    if settings.FXQ_CA_REQUIRED or settings.FXQ_DOCUMENT_SIGN_ENABLED:
        raise HTTPException(status_code=409, detail="电子病历尚未完成医师及医院数字签名")
    doctor = await db.get(Doctor, rx.doctor_id)
    patient = await db.get(Patient, rx.patient_id)
    data = compliance_service.generate_medical_record_pdf(
        rx,
        patient.name if patient else "患者",
        doctor.name if doctor else "医生",
    )
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="medical-record-{order_id}-preview.pdf"'
        },
    )


@router.get("/by-order/{order_id}", response_model=PrescriptionOut)
async def by_order(order_id: int, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rx = await rx_service.get_by_order(db, order_id)
    if not rx or rx.audit_status == "not_required" or not rx.items:
        raise HTTPException(status_code=404, detail="本次问诊未开具处方")
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    if not await _can_view_order_record(db, user, order):
        raise HTTPException(status_code=403, detail="无权查看该处方")
    return await _decorate(db, rx)


@router.get("/{order_id}/pdf")
async def pdf(order_id: int, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """处方 PDF；生产要求 CA 时，未签名文件禁止下载。"""
    rx = await rx_service.get_by_order(db, order_id)
    if not rx or rx.audit_status == "not_required" or not rx.items:
        raise HTTPException(status_code=404, detail="本次问诊未开具处方")
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
