"""医生与排班接口（M2，公开可读）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...schemas.doctor import DoctorOut, SlotOut
from ...services import doctor_service

router = APIRouter(prefix="/doctors", tags=["doctors"])


@router.get("", response_model=list[DoctorOut])
async def list_doctors(dept: str | None = None, db: AsyncSession = Depends(get_db)):
    return await doctor_service.list_doctors(db, dept)


@router.get("/{doctor_id}", response_model=DoctorOut)
async def get_doctor(doctor_id: int, db: AsyncSession = Depends(get_db)):
    d = await doctor_service.get_doctor(db, doctor_id)
    if not d:
        raise HTTPException(status_code=404, detail="医生不存在")
    return d


@router.get("/{doctor_id}/schedule", response_model=list[SlotOut])
async def get_schedule(doctor_id: int, day: str | None = None, db: AsyncSession = Depends(get_db)):
    return await doctor_service.get_schedule(db, doctor_id, day)
