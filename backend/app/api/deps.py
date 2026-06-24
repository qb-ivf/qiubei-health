"""接口依赖：当前登录用户 + RBAC 角色校验。"""
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.security import decode_token
from ..models.user import Doctor


async def get_current_user(authorization: str = Header(default="")) -> dict:
    token = authorization.replace("Bearer ", "").strip()
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="未登录或登录态已失效")
    return payload  # {sub, role, exp}


def get_current_user_id(user: dict = Depends(get_current_user)) -> int:
    return int(user["sub"])


def require_role(*roles: str):
    """角色守卫工厂：require_role('doctor') / require_role('pharmacist','admin')。"""
    async def _checker(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="无权限访问")
        return user
    return _checker


async def require_approved_doctor(
    user: dict = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    """医生守卫：必须是 role=doctor 且资质 approved（接诊/开方等核心动作）。"""
    if user.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="仅医生可访问")
    res = await db.execute(select(Doctor).where(Doctor.user_id == int(user["sub"])))
    doctor = res.scalar_one_or_none()
    if not doctor or doctor.audit_status != "approved":
        raise HTTPException(status_code=403, detail="医生资质未通过审核，暂不可接诊")
    return user
