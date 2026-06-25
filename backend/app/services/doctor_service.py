"""医生与排班服务（M2）：列表/详情/号源 + 开发 seed。"""
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.redis import redis_client
from ..models.drug import Drug
from ..models.schedule import Slot
from ..models.user import Doctor
from ..schemas.doctor import DoctorOut, SlotOut


class ScheduleError(Exception):
    """排班操作业务错误（号源冲突 / 不存在 / 不属于该医生）。"""


def slot_key(slot_id: int) -> str:
    return f"slot:remaining:{slot_id}"


async def _remaining(slot: Slot) -> int:
    val = await redis_client.get(slot_key(slot.id))
    return int(val) if val is not None else slot.remaining


def _slot_out(slot: Slot, remaining: int) -> SlotOut:
    return SlotOut(id=slot.id, day=slot.day, start_time=slot.start_time,
                   end_time=slot.end_time, remaining=remaining, quota=slot.quota)


async def create_slots(db: AsyncSession, doctor_id: int, day: str, times, quota: int) -> list[SlotOut]:
    """为某医生某天批量建号源（号源锁同步写 Redis）。同日同开始时间不重复建。

    times: 可迭代，元素具备 .start / .end（如 schemas.doctor.TimeRange）。
    医生端自助排班与运营后台代开号共用此逻辑，保证 Redis 一致、避免约满误判。
    """
    quota = max(1, quota)
    out: list[SlotOut] = []
    for t in times:
        exists = await db.scalar(
            select(Slot.id).where(Slot.doctor_id == doctor_id, Slot.day == day, Slot.start_time == t.start)
        )
        if exists:
            continue
        slot = Slot(doctor_id=doctor_id, day=day, start_time=t.start, end_time=t.end, quota=quota, remaining=quota)
        db.add(slot)
        await db.flush()
        await redis_client.set(slot_key(slot.id), quota)
        out.append(_slot_out(slot, quota))
    await db.commit()
    return out


async def set_slot_quota(db: AsyncSession, slot_id: int, quota: int, owner_doctor_id: int | None = None) -> SlotOut:
    """调整号源总号数（加号/减号）。已约的不能减到其以下。owner_doctor_id 非空时校验归属。"""
    slot = await db.get(Slot, slot_id)
    if not slot or (owner_doctor_id is not None and slot.doctor_id != owner_doctor_id):
        raise ScheduleError("号源不存在或不属于该医生")
    new_quota = max(1, quota)
    booked = slot.quota - await _remaining(slot)
    if new_quota < booked:
        raise ScheduleError(f"已约 {booked} 人，号数不能少于此")
    slot.quota = new_quota
    slot.remaining = new_quota - booked
    await db.commit()
    await redis_client.set(slot_key(slot_id), slot.remaining)
    return _slot_out(slot, slot.remaining)


async def delete_slot(db: AsyncSession, slot_id: int, owner_doctor_id: int | None = None) -> Slot:
    """删除号源（仅未被预约的可删）。owner_doctor_id 非空时校验归属。返回被删 slot 供审计。"""
    slot = await db.get(Slot, slot_id)
    if not slot or (owner_doctor_id is not None and slot.doctor_id != owner_doctor_id):
        raise ScheduleError("号源不存在或不属于该医生")
    if await _remaining(slot) < slot.quota:
        raise ScheduleError("该时段已有预约，不可删除")
    await db.delete(slot)
    await db.commit()
    await redis_client.delete(slot_key(slot_id))
    return slot


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
                           end_time=s.end_time, remaining=await _remaining(s), quota=s.quota))
    return out


async def seed_demo(db: AsyncSession) -> None:
    """开发期插入示例医生 + 未来 3 天号源（幂等）。"""
    # 药品字典 seed（幂等）
    drug_count = await db.scalar(select(func.count(Drug.id)))
    if not drug_count:
        for d in [
            dict(name="阿莫西林胶囊", spec="0.25g*24粒", price_fen=1850, category="处方药"),
            dict(name="布洛芬缓释胶囊", spec="0.3g*22粒", price_fen=2100, category="非处方药"),
            dict(name="连花清瘟胶囊", spec="0.35g*24粒", price_fen=1680, category="非处方药"),
            dict(name="盐酸哌替啶注射液", spec="50mg", price_fen=0, category="特殊限售药", restricted=True),
        ]:
            db.add(Drug(**d))
        await db.commit()

    count = await db.scalar(select(func.count(Doctor.id)).where(Doctor.name.is_not(None)))
    if count and count > 0:
        return

    # 就诊范围：中医科 / 内科 / 妇产科
    demos = [
        dict(user_id=1001, name="李国华", dept="中医科", title="主任医师",
             register_fee_fen=5000, good_at="中医内科调理、慢性病、亚健康", years=25),
        dict(user_id=1002, name="王建国", dept="内科", title="主任医师",
             register_fee_fen=4000, good_at="高血压、糖尿病、呼吸道感染等内科常见病", years=18),
        dict(user_id=1003, name="陈丽", dept="妇产科", title="副主任医师",
             register_fee_fen=4000, good_at="孕产期保健、月经不调、妇科常见病", years=15),
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
