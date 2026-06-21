"""接口依赖：当前登录用户 + RBAC 角色校验。"""
from fastapi import Depends, Header, HTTPException

from ..core.security import decode_token


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
