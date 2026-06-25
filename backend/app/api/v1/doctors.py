"""医生与排班接口（M2，公开可读）+ 医生本人资质/诊金/排班自助管理。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...constants import OrderStatus
from ...core.database import get_db
from ...core.redis import redis_client
from ...models.order import Order
from ...models.phrase import Phrase
from ...models.schedule import Slot
from ...models.user import Doctor
from ...schemas.doctor import (
    DoctorOut, DoctorProfileOut, FeeIn, PhraseIn, PhraseOut, QualificationIn, SlotOut, SlotQuotaIn, SlotsCreate,
)
from ...services import doctor_service
from ...services.doctor_service import slot_key
from ..deps import get_current_user_id, require_approved_doctor, require_role

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


async def _require_my_doctor(uid: int, db: AsyncSession) -> Doctor:
    res = await db.execute(select(Doctor).where(Doctor.user_id == uid))
    doctor = res.scalar_one_or_none()
    if not doctor:
        raise HTTPException(status_code=404, detail="医生记录不存在")
    return doctor


@router.post("/fee", response_model=DoctorProfileOut)
async def set_fee(body: FeeIn, user=Depends(require_approved_doctor), db: AsyncSession = Depends(get_db)):
    """医生设置本人挂号费（诊金设置）。"""
    if body.fee_fen < 0:
        raise HTTPException(status_code=400, detail="金额不能为负")
    doctor = await _require_my_doctor(int(user["sub"]), db)
    doctor.register_fee_fen = body.fee_fen
    await db.commit()
    await db.refresh(doctor)
    return doctor


@router.get("/my-schedule", response_model=list[SlotOut])
async def my_schedule(user=Depends(require_approved_doctor), db: AsyncSession = Depends(get_db)):
    """医生查看本人号源（排班管理）。"""
    doctor = await _require_my_doctor(int(user["sub"]), db)
    return await doctor_service.get_schedule(db, doctor.id, None)


@router.post("/slots", response_model=list[SlotOut])
async def create_slots(body: SlotsCreate, user=Depends(require_approved_doctor), db: AsyncSession = Depends(get_db)):
    """医生为某天批量建号源（号源锁同步写 Redis）。同日同开始时间不重复建。"""
    doctor = await _require_my_doctor(int(user["sub"]), db)
    quota = max(1, body.quota)
    out = []
    for t in body.times:
        exists = await db.scalar(
            select(Slot.id).where(Slot.doctor_id == doctor.id, Slot.day == body.day, Slot.start_time == t.start)
        )
        if exists:
            continue
        slot = Slot(doctor_id=doctor.id, day=body.day, start_time=t.start, end_time=t.end, quota=quota, remaining=quota)
        db.add(slot)
        await db.flush()
        await redis_client.set(slot_key(slot.id), quota)  # 号源锁
        out.append(SlotOut(id=slot.id, day=slot.day, start_time=slot.start_time, end_time=slot.end_time, remaining=quota, quota=quota))
    await db.commit()
    return out


@router.patch("/slots/{slot_id}", response_model=SlotOut)
async def update_slot_quota(slot_id: int, body: SlotQuotaIn, user=Depends(require_approved_doctor), db: AsyncSession = Depends(get_db)):
    """调整某号源的总号数（加号/减号）。已约的不能减到其以下。"""
    doctor = await _require_my_doctor(int(user["sub"]), db)
    slot = await db.get(Slot, slot_id)
    if not slot or slot.doctor_id != doctor.id:
        raise HTTPException(status_code=404, detail="号源不存在或不属于您")
    new_quota = max(1, body.quota)
    left = await redis_client.get(slot_key(slot_id))
    remaining = int(left) if left is not None else slot.remaining
    booked = slot.quota - remaining
    if new_quota < booked:
        raise HTTPException(status_code=409, detail=f"已约 {booked} 人，号数不能少于此")
    slot.quota = new_quota
    slot.remaining = new_quota - booked
    await db.commit()
    await redis_client.set(slot_key(slot_id), slot.remaining)
    return SlotOut(id=slot.id, day=slot.day, start_time=slot.start_time, end_time=slot.end_time,
                   remaining=slot.remaining, quota=slot.quota)


@router.delete("/slots/{slot_id}")
async def delete_slot(slot_id: int, user=Depends(require_approved_doctor), db: AsyncSession = Depends(get_db)):
    """医生删除本人某个号源（仅未被预约的可删）。"""
    doctor = await _require_my_doctor(int(user["sub"]), db)
    slot = await db.get(Slot, slot_id)
    if not slot or slot.doctor_id != doctor.id:
        raise HTTPException(status_code=404, detail="号源不存在或不属于您")
    left = await redis_client.get(slot_key(slot_id))
    remaining = int(left) if left is not None else slot.remaining
    if remaining < slot.quota:
        raise HTTPException(status_code=409, detail="该时段已有预约，不可删除")
    await db.delete(slot)
    await db.commit()
    await redis_client.delete(slot_key(slot_id))
    return {"ok": True}


# 已接诊：接诊过的订单（已进入问诊/审方/完成等，排除待支付/候诊/取消）
_CONSULTED = [
    int(OrderStatus.CONSULTING), int(OrderStatus.AUDITING), int(OrderStatus.REJECTED),
    int(OrderStatus.PRESCRIBED), int(OrderStatus.FINISHED), int(OrderStatus.REFUNDED),
]


@router.get("/phrases", response_model=list[PhraseOut])
async def list_phrases(uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """医生本人常用语列表。"""
    res = await db.execute(select(Phrase).where(Phrase.user_id == uid).order_by(Phrase.id.desc()))
    return res.scalars().all()


@router.post("/phrases", response_model=PhraseOut)
async def add_phrase(body: PhraseIn, user=Depends(require_role("doctor")), db: AsyncSession = Depends(get_db)):
    """新增常用语。"""
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="内容不能为空")
    phrase = Phrase(user_id=int(user["sub"]), content=content[:255])
    db.add(phrase)
    await db.commit()
    await db.refresh(phrase)
    return phrase


@router.delete("/phrases/{phrase_id}")
async def delete_phrase(phrase_id: int, user=Depends(require_role("doctor")), db: AsyncSession = Depends(get_db)):
    """删除本人常用语。"""
    phrase = await db.get(Phrase, phrase_id)
    if not phrase or phrase.user_id != int(user["sub"]):
        raise HTTPException(status_code=404, detail="常用语不存在")
    await db.delete(phrase)
    await db.commit()
    return {"ok": True}


@router.get("/stats")
async def my_stats(user=Depends(require_approved_doctor), db: AsyncSession = Depends(get_db)):
    """医生本人统计：累计已接诊数（工作台/大厅展示用）。"""
    doctor = await _require_my_doctor(int(user["sub"]), db)
    consulted = await db.scalar(
        select(func.count(Order.id)).where(Order.doctor_id == doctor.id, Order.status.in_(_CONSULTED))
    )
    return {"consulted": int(consulted or 0)}


@router.get("/{doctor_id}", response_model=DoctorOut)
async def get_doctor(doctor_id: int, db: AsyncSession = Depends(get_db)):
    d = await doctor_service.get_doctor(db, doctor_id)
    if not d:
        raise HTTPException(status_code=404, detail="医生不存在")
    return d


@router.get("/{doctor_id}/schedule", response_model=list[SlotOut])
async def get_schedule(doctor_id: int, day: str | None = None, db: AsyncSession = Depends(get_db)):
    return await doctor_service.get_schedule(db, doctor_id, day)
