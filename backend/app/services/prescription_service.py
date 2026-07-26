"""处方服务（M5）：开方提交 / 药师审方 / 驳回 + 特殊药拦截。"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import OrderStatus
from ..core.config import settings
from ..core.crypto import decrypt
from ..models.order import Order
from ..models.prescription import Prescription
from ..models.staff import Staff
from ..models.user import Doctor, Patient
from ..schemas.prescription import MedicalRecordComplete, PrescriptionCreate
from . import order_service

# 互联网医院严禁开具的特殊管理药（PRD §4.2）。生产应由药品字典 restricted 标记驱动。
SPECIAL_DRUG_KEYWORDS = ["哌替啶", "吗啡", "芬太尼", "氯胺酮", "地西泮注射", "可待因", "苯巴比妥"]


class RxError(Exception):
    """处方业务异常。"""

    def __init__(
        self,
        message: str,
        *,
        manual_review: bool = False,
        provider_code: int | None = None,
    ):
        super().__init__(message)
        self.manual_review = manual_review
        self.provider_code = provider_code


def _check_special(items: list) -> None:
    for it in items:
        name = (it.name if hasattr(it, "name") else it.get("name", "")) or ""
        if any(k in name for k in SPECIAL_DRUG_KEYWORDS):
            raise RxError(f"合规限制：本院不支持开具特殊管理药品「{name}」")


async def submit(db: AsyncSession, doctor_uid: int, data: PrescriptionCreate) -> Prescription:
    """医生开方提交：病历校验 + 特殊药拦截 + 订单 2→3（或驳回后 4→3）。"""
    if not data.diagnosis or len(data.diagnosis.strip()) < 2:
        raise RxError("初步诊断不能为空")
    if not data.chief or len(data.chief.strip()) < 2:
        raise RxError("主诉不能为空")
    if not data.present_illness or len(data.present_illness.strip()) < 2:
        raise RxError("现病史不能为空")
    if not data.items:
        raise RxError("处方至少应包含一种药品；如本次不开药，请使用“仅保存病历并结束问诊”")
    _check_special(data.items)

    order = await db.get(Order, data.order_id)
    if order is None:
        raise RxError("订单不存在")

    res = await db.execute(select(Doctor).where(Doctor.user_id == doctor_uid))
    doctor = res.scalar_one_or_none()
    if not doctor or doctor.id != order.doctor_id:
        raise RxError("当前账号不是该订单的接诊医生")

    doctor_ca = None
    enforce_ca = settings.FXQ_CA_REQUIRED or settings.FXQ_DOCUMENT_SIGN_ENABLED
    if enforce_ca:
        from . import ca_service

        doctor_ca = await ca_service.latest_success(db, "doctor", doctor.id)
        if not doctor_ca:
            raise RxError("开方医师尚未完成 CA 协议阅读及智能双录")

    cur = OrderStatus(order.status)
    if cur == OrderStatus.CONSULTING:
        await order_service.transition(db, order.id, OrderStatus.AUDITING, expect_from=OrderStatus.CONSULTING)
    elif cur == OrderStatus.REJECTED:
        await order_service.transition(db, order.id, OrderStatus.AUDITING, expect_from=OrderStatus.REJECTED)
    else:
        raise RxError(f"当前订单状态 {cur.name} 不可开方")

    # 复用同订单的处方记录（驳回重开时更新）
    res = await db.execute(select(Prescription).where(Prescription.order_id == order.id))
    rx = res.scalars().first()
    if rx is None:
        rx = Prescription(order_id=order.id, doctor_id=order.doctor_id, patient_id=order.patient_id)
        db.add(rx)

    rx.chief = data.chief
    rx.present_illness = data.present_illness
    rx.diagnosis = data.diagnosis
    rx.icd_code = data.icd_code
    rx.icd_name = data.icd_name
    rx.advice = data.advice
    rx.items = [it.model_dump() for it in data.items]
    rx.audit_status = "pending"
    rx.reject_reason = None
    # 重开处方会改变原文，旧签名与药师核验引用一律失效。
    rx.ca_sign = None
    rx.pdf_url = None
    rx.ca_sign_status = None
    rx.ca_verify_trade_no = None
    rx.ca_source_digest = None
    rx.ca_file_digest = None
    rx.ca_signature_count = None
    rx.ca_signed_at = None
    rx.ca_verify_report = None
    rx.doctor_ca_order_no = doctor_ca.order_no if doctor_ca else None
    rx.pharmacist_ca_order_no = None
    await db.flush()
    return rx


async def complete_without_prescription(
    db: AsyncSession,
    doctor_uid: int,
    order_id: int,
    data: MedicalRecordComplete,
) -> Prescription:
    """保存无药病历并完成问诊；不生成处方、不进入药师审方。"""
    if not data.diagnosis or len(data.diagnosis.strip()) < 2:
        raise RxError("初步诊断不能为空")
    if not data.chief or len(data.chief.strip()) < 2:
        raise RxError("主诉不能为空")
    if not data.present_illness or len(data.present_illness.strip()) < 2:
        raise RxError("现病史不能为空")
    if not data.icd_code or not data.icd_name:
        raise RxError("请选择 ICD-10 诊断")

    order_res = await db.execute(
        select(Order).where(Order.id == order_id).with_for_update()
    )
    order = order_res.scalar_one_or_none()
    if order is None:
        raise RxError("订单不存在")

    res = await db.execute(select(Doctor).where(Doctor.user_id == doctor_uid))
    doctor = res.scalar_one_or_none()
    if not doctor or doctor.id != order.doctor_id:
        raise RxError("当前账号不是该订单的接诊医生")

    doctor_ca = None
    enforce_ca = settings.FXQ_CA_REQUIRED or settings.FXQ_DOCUMENT_SIGN_ENABLED
    if enforce_ca:
        from . import ca_service

        doctor_ca = await ca_service.latest_success(db, "doctor", doctor.id)
        if not doctor_ca:
            raise RxError("接诊医师尚未完成 CA 协议阅读及智能双录")
    if settings.FXQ_CA_REQUIRED and not settings.FXQ_DOCUMENT_SIGN_ENABLED:
        raise RxError("生产 CA 门禁已开启，但真实电子病历签署尚未启用")

    cur = OrderStatus(order.status)
    if cur not in (OrderStatus.CONSULTING, OrderStatus.REJECTED):
        raise RxError(f"当前订单状态 {cur.name} 不可按无药问诊完成")

    # 沿用 prescriptions 表中的 EMR 字段；not_required 明确区分“病历”与“处方”。
    res = await db.execute(select(Prescription).where(Prescription.order_id == order.id))
    rx = res.scalars().first()
    if rx is not None and rx.ca_sign_status == "manual_review":
        raise RxError("上次放心签调用结果待人工确认，禁止重复签署")
    if rx is None:
        rx = Prescription(order_id=order.id, doctor_id=order.doctor_id, patient_id=order.patient_id)
        db.add(rx)

    _fill_no_prescription_record(
        rx,
        data,
        doctor_ca_order_no=doctor_ca.order_no if doctor_ca else None,
    )
    await db.flush()

    if settings.FXQ_DOCUMENT_SIGN_ENABLED:
        from . import compliance_service, fxq_document_service

        patient = await db.get(Patient, order.patient_id)
        if not doctor.name or not doctor.id_card_enc:
            raise RxError("接诊医师实名资料不完整，无法完成电子病历签署")
        if not patient or not patient.name:
            raise RxError("患者资料不完整，无法生成电子病历原文")
        try:
            doctor_id_no = decrypt(doctor.id_card_enc)
        except Exception as exc:  # noqa: BLE001
            raise RxError("医师身份证密文无法解密，请重新完成备案") from exc
        if not doctor_id_no or len(doctor_id_no) != 18:
            raise RxError("接诊医师备案身份证格式不正确")

        source_pdf = compliance_service.generate_medical_record_pdf(
            rx,
            patient.name,
            doctor.name,
            for_signing=True,
        )
        try:
            signed = await fxq_document_service.sign_medical_record_pdf(
                source_pdf,
                doctor_name=doctor.name,
                doctor_id_no=doctor_id_no,
            )
            rx.pdf_url = fxq_document_service.store_signed_pdf(
                rx.id, signed.signed_pdf, signed.file_digest
            )
        except fxq_document_service.FxqDocumentError as exc:
            raise RxError(
                f"放心签电子病历签署未完成：{exc}",
                manual_review=exc.manual_review,
                provider_code=exc.provider_code,
            ) from exc
        rx.ca_sign = signed.sign_trade_no
        rx.ca_sign_status = "verified"
        rx.ca_verify_trade_no = signed.verify_trade_no
        rx.ca_source_digest = signed.source_digest
        rx.ca_file_digest = signed.file_digest
        rx.ca_signature_count = signed.signature_count
        rx.ca_signed_at = signed.signed_at
        rx.ca_verify_report = signed.verify_report

    # 文档签署成功（或开发环境未启用签署）后才允许订单进入完成态。
    await order_service.transition(db, order.id, OrderStatus.FINISHED, expect_from=cur)
    from . import finance_service, notification_service

    await finance_service.record_ledger(db, order)
    await notification_service.notify(
        db,
        order.user_id,
        "consultation",
        "问诊已完成",
        "医生已完成电子病历，本次未开具药品，请按医嘱处理。",
        order.id,
    )
    return rx


def _fill_no_prescription_record(
    rx: Prescription,
    data: MedicalRecordComplete,
    *,
    doctor_ca_order_no: str | None,
) -> None:
    rx.chief = data.chief
    rx.present_illness = data.present_illness
    rx.diagnosis = data.diagnosis.strip()
    rx.icd_code = data.icd_code
    rx.icd_name = data.icd_name
    rx.advice = data.advice
    rx.items = []
    rx.audit_status = "not_required"
    rx.reject_reason = None
    rx.recipe_unique_id = None
    rx.checked_at = None
    rx.audit_staff_id = None
    rx.ca_sign = None
    rx.pdf_url = None
    rx.ca_sign_status = None
    rx.ca_verify_trade_no = None
    rx.ca_source_digest = None
    rx.ca_file_digest = None
    rx.ca_signature_count = None
    rx.ca_signed_at = None
    rx.ca_verify_report = None
    rx.doctor_ca_order_no = doctor_ca_order_no
    rx.pharmacist_ca_order_no = None


async def stage_no_prescription_manual_review(
    db: AsyncSession,
    doctor_uid: int,
    order_id: int,
    data: MedicalRecordComplete,
) -> Prescription:
    """供应商结果不确定时，在原事务回滚后保留病历原文并锁定重复签署。"""
    order = await db.get(Order, order_id)
    if order is None:
        raise RxError("订单不存在")
    res = await db.execute(select(Doctor).where(Doctor.user_id == doctor_uid))
    doctor = res.scalar_one_or_none()
    if not doctor or doctor.id != order.doctor_id:
        raise RxError("当前账号不是该订单的接诊医生")
    if OrderStatus(order.status) not in (OrderStatus.CONSULTING, OrderStatus.REJECTED):
        raise RxError("订单已不处于可完成状态")

    res = await db.execute(select(Prescription).where(Prescription.order_id == order.id))
    rx = res.scalars().first()
    if rx is None:
        rx = Prescription(order_id=order.id, doctor_id=order.doctor_id, patient_id=order.patient_id)
        db.add(rx)
    _fill_no_prescription_record(rx, data, doctor_ca_order_no=None)
    rx.ca_sign_status = "manual_review"
    await db.flush()
    return rx


async def list_pending(db: AsyncSession) -> list[Prescription]:
    res = await db.execute(select(Prescription).where(Prescription.audit_status == "pending").order_by(Prescription.id.asc()))
    return list(res.scalars().all())


async def approve(db: AsyncSession, rx_id: int, staff_id: int | None = None) -> Prescription:
    """药师审核通过：校验双录，按配置完成三方 PDF 签署/验签，再执行订单 3→5。"""
    import uuid
    from datetime import datetime, timezone

    staff = await db.get(Staff, staff_id) if staff_id else None
    if staff is None or not staff.active or not staff.name or not staff.id_card_enc:
        raise RxError("审方账号未补录有效的真实姓名和身份证，请先在账号管理完成监管备案")

    res = await db.execute(
        select(Prescription).where(Prescription.id == rx_id).with_for_update()
    )
    rx = res.scalar_one_or_none()
    if rx is None or rx.audit_status != "pending":
        raise RxError("处方不存在或已处理")
    if rx.ca_sign_status == "manual_review":
        raise RxError("上次放心签调用结果待人工确认，禁止重复签署")

    pharmacist_ca = doctor_ca = None
    enforce_ca = settings.FXQ_CA_REQUIRED or settings.FXQ_DOCUMENT_SIGN_ENABLED
    if enforce_ca:
        from . import ca_service

        if staff.role != "pharmacist":
            raise RxError("管理员不能代替药师完成 CA 审方签署")
        pharmacist_ca = await ca_service.latest_success(db, "staff", staff.id)
        if not pharmacist_ca:
            raise RxError("审方药师尚未完成 CA 协议阅读及智能双录")
        doctor_ca = await ca_service.latest_success(db, "doctor", rx.doctor_id)
        if not doctor_ca:
            raise RxError("开方医师尚未完成 CA 协议阅读及智能双录")

    if settings.FXQ_CA_REQUIRED and not settings.FXQ_DOCUMENT_SIGN_ENABLED:
        raise RxError("生产 CA 门禁已开启，但真实处方 PDF 签署尚未启用")

    rx.ca_sign = None
    rx.pdf_url = None
    rx.ca_sign_status = None
    rx.ca_verify_trade_no = None
    rx.ca_source_digest = None
    rx.ca_file_digest = None
    rx.ca_signature_count = None
    rx.ca_signed_at = None
    rx.ca_verify_report = None
    if doctor_ca:
        rx.doctor_ca_order_no = doctor_ca.order_no
    if pharmacist_ca:
        rx.pharmacist_ca_order_no = pharmacist_ca.order_no
    # 天津监管（S3）：处方唯一号（对外备查/核销）+ 审方时间 + 审方药师
    rx.recipe_unique_id = rx.recipe_unique_id or uuid.uuid4().hex
    rx.checked_at = datetime.now(timezone.utc).replace(tzinfo=None)
    rx.audit_staff_id = staff_id

    if settings.FXQ_DOCUMENT_SIGN_ENABLED:
        from . import compliance_service, fxq_document_service

        doctor = await db.get(Doctor, rx.doctor_id)
        patient = await db.get(Patient, rx.patient_id)
        if not doctor or not doctor.name or not doctor.id_card_enc:
            raise RxError("开方医师实名资料不完整，无法完成处方签署")
        if not patient or not patient.name:
            raise RxError("患者资料不完整，无法生成处方原文")
        try:
            doctor_id_no = decrypt(doctor.id_card_enc)
            pharmacist_id_no = decrypt(staff.id_card_enc)
        except Exception as exc:  # noqa: BLE001
            raise RxError("医师或药师身份证密文无法解密，请重新完成备案") from exc
        if not doctor_id_no or len(doctor_id_no) != 18:
            raise RxError("开方医师备案身份证格式不正确")
        if not pharmacist_id_no or len(pharmacist_id_no) != 18:
            raise RxError("审方药师备案身份证格式不正确")

        source_pdf = compliance_service.generate_prescription_pdf(
            rx,
            patient.name,
            doctor.name,
            staff.name,
            for_signing=True,
        )
        try:
            signed = await fxq_document_service.sign_prescription_pdf(
                source_pdf,
                doctor_name=doctor.name,
                doctor_id_no=doctor_id_no,
                pharmacist_name=staff.name,
                pharmacist_id_no=pharmacist_id_no,
            )
            rx.pdf_url = fxq_document_service.store_signed_pdf(
                rx.id, signed.signed_pdf, signed.file_digest
            )
        except fxq_document_service.FxqDocumentError as exc:
            raise RxError(
                f"放心签处方签署未完成：{exc}",
                manual_review=exc.manual_review,
                provider_code=exc.provider_code,
            ) from exc
        rx.ca_sign = signed.sign_trade_no
        rx.ca_sign_status = "verified"
        rx.ca_verify_trade_no = signed.verify_trade_no
        rx.ca_source_digest = signed.source_digest
        rx.ca_file_digest = signed.file_digest
        rx.ca_signature_count = signed.signature_count
        rx.ca_signed_at = signed.signed_at
        rx.ca_verify_report = signed.verify_report

    await order_service.transition(db, rx.order_id, OrderStatus.PRESCRIBED, expect_from=OrderStatus.AUDITING)
    rx.audit_status = "approved"

    # 审核通过后计算药费，落到订单（M6 药费支付用）
    order = await db.get(Order, rx.order_id)
    if order is not None:
        order.drug_fee_fen = sum(int(it.get("price_fen", 0)) * int(it.get("qty", 1)) for it in (rx.items or []))
        from . import notification_service
        await notification_service.notify(
            db, order.user_id, "rx", "处方已通过", "药师审核通过，请尽快缴纳药费", order.id
        )
    await db.flush()
    return rx


async def mark_signing_manual_review(
    db: AsyncSession, rx_id: int
) -> Prescription | None:
    """供应商结果不确定时持久化锁定；必须在原审方事务回滚后调用。"""
    res = await db.execute(
        select(Prescription).where(Prescription.id == rx_id).with_for_update()
    )
    rx = res.scalar_one_or_none()
    if rx is None or rx.audit_status != "pending":
        return rx
    rx.ca_sign_status = "manual_review"
    await db.flush()
    return rx


async def clear_signing_manual_review(
    db: AsyncSession, rx_id: int
) -> Prescription:
    """管理员取得供应商“未签署”确认后解除处方或病历的重复签署锁。"""
    res = await db.execute(
        select(Prescription).where(Prescription.id == rx_id).with_for_update()
    )
    rx = res.scalar_one_or_none()
    if rx is None:
        raise RxError("诊疗文档不存在")
    if rx.audit_status not in {"pending", "not_required"} or rx.ca_sign_status != "manual_review":
        raise RxError("该诊疗文档不处于 CA 结果待人工确认状态")
    rx.ca_sign_status = "failed"
    await db.flush()
    return rx


async def reject(db: AsyncSession, rx_id: int, reason: str) -> Prescription:
    """药师驳回：订单 3→4 + 驳回理由。"""
    rx = await db.get(Prescription, rx_id)
    if rx is None or rx.audit_status != "pending":
        raise RxError("处方不存在或已处理")
    if rx.ca_sign_status == "manual_review":
        raise RxError("上次放心签调用结果待人工确认，禁止驳回或重复签署")
    if not reason.strip():
        raise RxError("驳回原因不能为空")
    await order_service.transition(db, rx.order_id, OrderStatus.REJECTED, expect_from=OrderStatus.AUDITING)
    rx.audit_status = "rejected"
    rx.reject_reason = reason
    await db.flush()
    return rx


async def get_by_order(db: AsyncSession, order_id: int) -> Prescription | None:
    res = await db.execute(select(Prescription).where(Prescription.order_id == order_id))
    return res.scalars().first()
