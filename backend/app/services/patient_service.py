"""就诊人服务（M1）：实名校验 + 加密落库 + 脱敏返回。"""
import re

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.crypto import decrypt, encrypt
from ..core.security import mask_id_card, mask_name
from ..models.user import Patient
from ..schemas.patient import PatientCreate, PatientOut

_ID_RE = re.compile(r"^\d{17}[\dXx]$")


def real_name_verify(name: str, id_card: str) -> bool:
    """二要素实名核验。开发期仅做身份证格式校验；生产对接公安/三方核验。"""
    return bool(name and _ID_RE.match(id_card or ""))


def _to_out(p: Patient) -> PatientOut:
    idc = None
    try:
        idc = decrypt(p.id_card_enc) if p.id_card_enc else None
    except Exception:  # noqa: BLE001 解密失败（换过密钥等）
        idc = None
    return PatientOut(
        id=p.id, name=mask_name(p.name), id_card=mask_id_card(idc) if idc else "(已加密)",
        gender=p.gender, relation=p.relation, verified=p.verified, is_default=p.is_default,
    )


async def create_patient(db: AsyncSession, user_id: int, data: PatientCreate) -> PatientOut:
    if not real_name_verify(data.name, data.id_card):
        raise ValueError("实名信息不合法（姓名或身份证号有误）")

    res = await db.execute(select(Patient).where(Patient.user_id == user_id))
    first = res.scalars().first() is None  # 首个就诊人设为默认

    patient = Patient(
        user_id=user_id, name=data.name, id_card_enc=encrypt(data.id_card),
        gender=data.gender, relation=data.relation, verified=True, is_default=first,
    )
    db.add(patient)
    await db.flush()
    return _to_out(patient)


async def list_patients(db: AsyncSession, user_id: int) -> list[PatientOut]:
    res = await db.execute(select(Patient).where(Patient.user_id == user_id))
    return [_to_out(p) for p in res.scalars().all()]


async def set_default(db: AsyncSession, user_id: int, patient_id: int) -> None:
    await db.execute(update(Patient).where(Patient.user_id == user_id).values(is_default=False))
    await db.execute(
        update(Patient).where(Patient.id == patient_id, Patient.user_id == user_id).values(is_default=True)
    )


async def delete_patient(db: AsyncSession, user_id: int, patient_id: int) -> None:
    res = await db.execute(select(Patient).where(Patient.id == patient_id, Patient.user_id == user_id))
    p = res.scalar_one_or_none()
    if not p:
        raise ValueError("就诊人不存在")
    was_default = p.is_default
    await db.delete(p)
    await db.flush()
    if was_default:  # 删的是默认就诊人 → 另选一个设为默认
        res = await db.execute(select(Patient).where(Patient.user_id == user_id).limit(1))
        other = res.scalar_one_or_none()
        if other:
            other.is_default = True
            await db.flush()
