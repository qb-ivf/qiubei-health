"""运营后台员工账号服务（RBAC 登录 + 账号管理）。"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.security import hash_password, verify_password
from ..models.staff import Staff


async def authenticate(db: AsyncSession, username: str, password: str) -> Staff | None:
    """校验账号密码；成功返回 Staff，失败返回 None（不区分账号/密码错误，防枚举）。"""
    if not username or not password:
        return None
    res = await db.execute(select(Staff).where(Staff.username == username, Staff.active.is_(True)))
    staff = res.scalar_one_or_none()
    if not staff or not verify_password(password, staff.password_hash):
        return None
    return staff


class StaffError(Exception):
    pass


VALID_ROLES = {"admin", "pharmacist", "finance"}


async def list_staff(db: AsyncSession) -> list[Staff]:
    res = await db.execute(select(Staff).order_by(Staff.id.asc()))
    return list(res.scalars().all())


async def create_staff(db: AsyncSession, username: str, password: str, role: str, name: str | None) -> Staff:
    if not username or not password:
        raise StaffError("用户名和密码不能为空")
    if role not in VALID_ROLES:
        raise StaffError("角色不合法")
    res = await db.execute(select(Staff).where(Staff.username == username))
    if res.scalar_one_or_none():
        raise StaffError("用户名已存在")
    staff = Staff(username=username, password_hash=hash_password(password), role=role, name=name or username)
    db.add(staff)
    await db.flush()
    return staff


async def update_staff(db: AsyncSession, staff_id: int, *, name=None, role=None, active=None) -> Staff:
    staff = await db.get(Staff, staff_id)
    if not staff:
        raise StaffError("账号不存在")
    if role is not None:
        if role not in VALID_ROLES:
            raise StaffError("角色不合法")
        staff.role = role
    if name is not None:
        staff.name = name
    if active is not None:
        staff.active = bool(active)
    await db.flush()
    return staff


async def reset_password(db: AsyncSession, staff_id: int, password: str) -> Staff:
    staff = await db.get(Staff, staff_id)
    if not staff:
        raise StaffError("账号不存在")
    if not password:
        raise StaffError("新密码不能为空")
    staff.password_hash = hash_password(password)
    await db.flush()
    return staff


async def delete_staff(db: AsyncSession, staff_id: int) -> None:
    staff = await db.get(Staff, staff_id)
    if not staff:
        raise StaffError("账号不存在")
    await db.delete(staff)
    await db.flush()


async def count_active_admins(db: AsyncSession) -> int:
    from sqlalchemy import func
    return await db.scalar(
        select(func.count()).select_from(Staff).where(Staff.role == "admin", Staff.active.is_(True))
    )


async def upsert(db: AsyncSession, username: str, password: str, role: str, name: str | None = None) -> Staff:
    """创建或重置一个员工账号（脚本用）。"""
    res = await db.execute(select(Staff).where(Staff.username == username))
    staff = res.scalar_one_or_none()
    if staff:
        staff.password_hash = hash_password(password)
        staff.role = role
        staff.active = True
        if name:
            staff.name = name
    else:
        staff = Staff(username=username, password_hash=hash_password(password), role=role, name=name or username)
        db.add(staff)
    await db.flush()
    return staff
