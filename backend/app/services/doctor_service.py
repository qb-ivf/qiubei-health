"""医生与排班服务（M2）：列表/详情/号源 + 开发 seed。"""
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.redis import redis_client
from ..models.schedule import Slot
from ..models.user import Doctor
from ..schemas.doctor import DoctorOut, SlotOut


def slot_key(slot_id: int) -> str:
    return f"slot:remaining:{slot_id}"


async def _remaining(slot: Slot) -> int:
    val = await redis_client.get(slot_key(slot.id))
    return int(val) if val is not None else slot.remaining


async def list_doctors(db: AsyncSession, dept: str | None = None) -> list[DoctorOut]:
    stmt = select(Doctor).where(Doctor.audit_status == "approved", Doctor.name.is_not(None))
    if dept:
        stmt = stmt.where(Doctor.dept == dept)
    res = await db.execute(stmt)
    return [DoctorOut.model_validate(d) for d in res.scalars().all()]


async def get_doctor(db: AsyncSession, doctor_id: int) -> DoctorOut | None:
    d = await db.get(Doctor, doctor_id)
    return DoctorOut.model_validate(d) if d else None


async def get_schedule(db: AsyncSession, doctor_id: int, day: str | None) -> list[SlotOut]:
    stmt = select(Slot).where(Slot.doctor_id == doctor_id)
    if day:
        stmt = stmt.where(Slot.day == day)
    res = await db.execute(stmt.order_by(Slot.day, Slot.start_time))
    out = []
    for s in res.scalars().all():
        out.append(SlotOut(id=s.id, day=s.day, start_time=s.start_time,
                           end_time=s.end_time, remaining=await _remaining(s)))
    return out


async def seed_demo(db: AsyncSession) -> None:
    """开发期插入示例医生 + 未来 3 天号源（幂等）。"""
    count = await db.scalar(select(func.count(Doctor.id)).where(Doctor.name.is_not(None)))
    if count and count > 0:
        return

    demos = [
        dict(user_id=1001, name="张建设", dept="呼吸内科", title="主任医师",
             register_fee_fen=5000, good_at="慢阻肺、哮喘、肺部感染等呼吸系统疾病诊治", years=25),
        dict(user_id=1002, name="王美丽", dept="呼吸内科", title="副主任医师",
             register_fee_fen=4000, good_at="慢性咳嗽、支气管炎、过敏性鼻炎", years=15),
        dict(user_id=1003, name="李晓梅", dept="儿科", title="副主任医师",
             register_fee_fen=4000, good_at="小儿呼吸道感染、发热、消化不良", years=12),
    ]
    times = [("09:00", "09:30"), ("09:30", "10:00"), ("10:00", "10:30")]
    today = date.today()

    for d in demos:
        doctor = Doctor(audit_status="approved", **d)
        db.add(doctor)
        await db.flush()
        for offset in range(3):
            day = (today + timedelta(days=offset)).isoformat()
            for st, et in times:
                slot = Slot(doctor_id=doctor.id, day=day, start_time=st, end_time=et, quota=5, remaining=5)
                db.add(slot)
                await db.flush()
                await redis_client.set(slot_key(slot.id), 5)
    await db.commit()
