"""医生与排班接口（M2，公开可读）+ 医生本人资质提交/查询。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...models.user import Doctor
from ...schemas.doctor import DoctorOut, DoctorProfileOut, QualificationIn, SlotOut
from ...services import doctor_service
from ..deps import get_current_user_id, require_role

router = APIRouter(prefix="/doctors", tags=["doctors"])


@router.get("", response_model=list[DoctorOut])
async def list_doctors(dept: str | None = None, db: AsyncSession = Depends(get_db)):
    return await doctor_service.list_doctors(db, dept)


# 注意：以下固定路径需在 /{doctor_id} 之前注册，否则会被路径参数捕获。
@router.get("/profile", response_model=DoctorProfileOut)
async def my_profile(uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """医生本人档案（含审核状态）。"""
    res = await db.execute(select(Doctor).where(Doctor.user_id == uid))
    doctor = res.scalar_one_or_none()
    if not doctor:
        raise HTTPException(status_code=404, detail="医生记录不存在")
    return doctor


@router.post("/qualification", response_model=DoctorProfileOut)
async def submit_qualification(
    body: QualificationIn, user=Depends(require_role("doctor")), db: AsyncSession = Depends(get_db)
):
    """医生提交/更新执业资质 → 置 pending，等待 admin 终审。"""
    uid = int(user["sub"])
    res = await db.execute(select(Doctor).where(Doctor.user_id == uid))
    doctor = res.scalar_one_or_none()
    if not doctor:
        doctor = Doctor(user_id=uid)
        db.add(doctor)
    doctor.name = body.name
    doctor.license_no = body.license_no
    doctor.practice_no = body.practice_no
    doctor.dept = body.dept
    doctor.title = body.title
    doctor.good_at = body.good_at
    doctor.years = body.years
    doctor.audit_status = "pending"  # 提交即重置为待审
    await db.commit()
    await db.refresh(doctor)
    return doctor


@router.get("/{doctor_id}", response_model=DoctorOut)
async def get_doctor(doctor_id: int, db: AsyncSession = Depends(get_db)):
    d = await doctor_service.get_doctor(db, doctor_id)
    if not d:
        raise HTTPException(status_code=404, detail="医生不存在")
    return d


@router.get("/{doctor_id}/schedule", response_model=list[SlotOut])
async def get_schedule(doctor_id: int, day: str | None = None, db: AsyncSession = Depends(get_db)):
    return await doctor_service.get_schedule(db, doctor_id, day)
