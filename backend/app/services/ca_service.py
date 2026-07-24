"""放心签高级证书协议/智能双录业务服务。"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.crypto import decrypt, encrypt
from ..models.ca_enrollment import CaEnrollment
from ..models.staff import Staff
from ..models.user import Doctor
from .fxq_ca import FxqCaError, config_errors, fxq_ca_client

CN_TZ = timezone(timedelta(hours=8))
PENDING_FACE_CODES = {"6010", "1506", "9999"}


class CaEnrollmentError(Exception):
    """本地证书双录业务错误。"""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _parse_occurred_time(value) -> datetime | None:
    if not value:
        return None
    try:
        local = datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S").replace(tzinfo=CN_TZ)
        return local.astimezone(timezone.utc).replace(tzinfo=None)
    except ValueError:
        return None


async def _subject_for_user(db: AsyncSession, user: dict) -> tuple[str, int, str, str]:
    role = user.get("role")
    uid = int(user["sub"])
    if role == "doctor":
        res = await db.execute(select(Doctor).where(Doctor.user_id == uid))
        doctor = res.scalar_one_or_none()
        if not doctor or doctor.audit_status != "approved":
            raise CaEnrollmentError("医生资质尚未通过，不能发起 CA 双录")
        name, id_enc = doctor.name, doctor.id_card_enc
        subject_type, subject_id = "doctor", doctor.id
    elif role == "pharmacist":
        staff = await db.get(Staff, uid)
        if not staff or not staff.active:
            raise CaEnrollmentError("药师账号不存在或已停用")
        name, id_enc = staff.name, staff.id_card_enc
        subject_type, subject_id = "staff", staff.id
    else:
        raise CaEnrollmentError("仅医生或药师本人可以完成 CA 双录")
    if not name or not id_enc:
        raise CaEnrollmentError("姓名或身份证尚未完成医院备案")
    try:
        id_no = decrypt(id_enc)
    except Exception as exc:  # noqa: BLE001
        raise CaEnrollmentError("身份证密文无法解密，请联系管理员重新备案") from exc
    if not id_no or len(id_no) != 18:
        raise CaEnrollmentError("备案身份证格式不正确")
    return subject_type, subject_id, name, id_no


async def latest_for_subject(db: AsyncSession, subject_type: str, subject_id: int) -> CaEnrollment | None:
    res = await db.execute(
        select(CaEnrollment)
        .where(CaEnrollment.subject_type == subject_type, CaEnrollment.subject_id == subject_id)
        .order_by(CaEnrollment.id.desc())
        .limit(1)
    )
    return res.scalars().first()


async def latest_for_user(db: AsyncSession, user: dict) -> CaEnrollment | None:
    subject_type, subject_id, _, _ = await _subject_for_user(db, user)
    return await latest_for_subject(db, subject_type, subject_id)


async def latest_success(db: AsyncSession, subject_type: str, subject_id: int) -> CaEnrollment | None:
    res = await db.execute(
        select(CaEnrollment)
        .where(
            CaEnrollment.subject_type == subject_type,
            CaEnrollment.subject_id == subject_id,
            CaEnrollment.status == "succeeded",
        )
        .order_by(CaEnrollment.id.desc())
        .limit(1)
    )
    return res.scalars().first()


async def require_user_verified(db: AsyncSession, user: dict) -> CaEnrollment | None:
    """生产开关开启时强制当前医师/药师已有成功双录记录。"""
    if not settings.FXQ_CA_REQUIRED:
        return None
    subject_type, subject_id, _, _ = await _subject_for_user(db, user)
    enrollment = await latest_success(db, subject_type, subject_id)
    if not enrollment:
        raise CaEnrollmentError("尚未完成 CA 协议阅读及智能双录")
    return enrollment


async def require_doctor_verified(db: AsyncSession, doctor_id: int) -> CaEnrollment | None:
    if not settings.FXQ_CA_REQUIRED:
        return None
    enrollment = await latest_success(db, "doctor", doctor_id)
    if not enrollment:
        raise CaEnrollmentError("开方医师尚未完成 CA 协议阅读及智能双录")
    return enrollment


async def start_enrollment(db: AsyncSession, user: dict) -> tuple[CaEnrollment, str | None]:
    if not settings.FXQ_CA_ENABLED:
        raise CaEnrollmentError("FXQ_CA_ENABLED 未开启")
    errors = config_errors(settings)
    if errors:
        raise CaEnrollmentError("；".join(errors))
    subject_type, subject_id, name, id_no = await _subject_for_user(db, user)
    existing = await latest_for_subject(db, subject_type, subject_id)
    if existing and existing.status == "succeeded":
        return existing, None
    if (
        existing
        and existing.status == "pending"
        and existing.created_at
        and existing.created_at >= _utcnow() - timedelta(seconds=120)
        and existing.agreement_url_enc
    ):
        try:
            return existing, decrypt(existing.agreement_url_enc)
        except Exception:  # noqa: BLE001
            pass

    order_no = f"QBCA{datetime.now(CN_TZ):%Y%m%d%H%M%S}{uuid.uuid4().hex[:10].upper()}"
    provider_user_id = f"qb_{subject_type}_{subject_id}"
    result = await fxq_ca_client.start_agreement(
        name=name,
        id_no=id_no,
        redirect_url=settings.FXQ_CA_REDIRECT_URL,
        user_id=provider_user_id,
        order_no=order_no,
    )
    verify_id = result.data.get("verifyId")
    agreement_url = result.data.get("agreementUrl")
    if not verify_id or not agreement_url:
        raise FxqCaError("放心签响应缺少 verifyId 或 agreementUrl")

    enrollment = CaEnrollment(
        subject_type=subject_type,
        subject_id=subject_id,
        provider_user_id=provider_user_id,
        order_no=order_no,
        verify_id=str(verify_id)[:64],
        trade_no=result.trade_no,
        status="pending",
        agreement_url_enc=encrypt(str(agreement_url)),
        provider_code=str(result.code),
        provider_msg=result.msg,
    )
    db.add(enrollment)
    await db.flush()
    return enrollment, str(agreement_url)


def user_owns_enrollment(enrollment: CaEnrollment, user: dict) -> bool:
    role, uid = user.get("role"), int(user["sub"])
    if role == "pharmacist":
        return enrollment.subject_type == "staff" and enrollment.subject_id == uid
    return role == "doctor"  # 医生的 user.id 与 doctors.id 不同，调用方应通过 _subject_for_user 再核对


async def enrollment_for_user(db: AsyncSession, order_no: str, user: dict) -> CaEnrollment:
    res = await db.execute(select(CaEnrollment).where(CaEnrollment.order_no == order_no))
    enrollment = res.scalar_one_or_none()
    if not enrollment:
        raise CaEnrollmentError("CA 双录记录不存在")
    subject_type, subject_id, _, _ = await _subject_for_user(db, user)
    if enrollment.subject_type != subject_type or enrollment.subject_id != subject_id:
        raise CaEnrollmentError("无权查看该 CA 双录记录")
    return enrollment


async def refresh_enrollment(enrollment: CaEnrollment) -> CaEnrollment:
    if enrollment.status in {"succeeded", "failed", "expired"}:
        return enrollment
    result = await fxq_ca_client.query_result(order_no=enrollment.order_no)
    data = result.data
    face_code = str(data.get("faceCode") or "")
    enrollment.provider_code = str(result.code)
    enrollment.face_code = face_code[:16] or None
    enrollment.provider_msg = str(data.get("faceMsg") or result.msg or "")[:255] or None
    enrollment.live_rate = str(data.get("liveRate"))[:16] if data.get("liveRate") is not None else None
    enrollment.similarity = str(data.get("similarity"))[:16] if data.get("similarity") is not None else None
    enrollment.occurred_at = _parse_occurred_time(data.get("occurredTime"))
    enrollment.last_checked_at = _utcnow()
    if face_code == "0":
        enrollment.status = "succeeded"
        enrollment.completed_at = enrollment.completed_at or _utcnow()
        enrollment.agreement_url_enc = None
    elif face_code == "2002":
        enrollment.status = "expired"
        enrollment.agreement_url_enc = None
    elif face_code and face_code not in PENDING_FACE_CODES:
        enrollment.status = "failed"
        enrollment.agreement_url_enc = None
    else:
        enrollment.status = "pending"
    return enrollment
