"""就诊人接口（M1，需登录）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...schemas.patient import PatientCreate, PatientOut, PatientUpdate
from ...services import patient_service
from ..deps import get_current_user_id

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=list[PatientOut])
async def list_patients(uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    return await patient_service.list_patients(db, uid)


@router.post("", response_model=PatientOut)
async def add_patient(
    body: PatientCreate, uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
):
    try:
        out = await patient_service.create_patient(db, uid, body)
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    return out


@router.put("/{patient_id}", response_model=PatientOut)
async def update_patient(
    patient_id: int, body: PatientUpdate, uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
):
    """编辑就诊人（姓名/性别/关系/手机号；改手机号需验证码）。"""
    try:
        out = await patient_service.update_patient(db, uid, patient_id, body)
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(e))
    return out


@router.put("/{patient_id}/default")
async def set_default(
    patient_id: int, uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
):
    await patient_service.set_default(db, uid, patient_id)
    await db.commit()
    return {"code": 0}


@router.delete("/{patient_id}")
async def delete_patient(
    patient_id: int, uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)
):
    try:
        await patient_service.delete_patient(db, uid, patient_id)
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=404, detail=str(e))
    return {"ok": True}
