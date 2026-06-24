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
