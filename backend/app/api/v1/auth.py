"""鉴权接口（M1）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.crypto import decrypt
from ...core.database import get_db
from ...core.security import create_token, mask_phone
from ...models.user import User
from ...schemas.auth import AdminLogin, Me, TokenOut, WxLogin
from ...services import auth_service, staff_service
from ..deps import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
async def patient_login(body: WxLogin, db: AsyncSession = Depends(get_db)):
    try:
        user, token = await auth_service.login_patient(db, body.code, body.phone_code, body.dev_phone)
        await db.commit()
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return TokenOut(token=token, role=user.role, user_id=user.id)


@router.post("/doctor/login", response_model=TokenOut)
async def doctor_login(body: WxLogin, db: AsyncSession = Depends(get_db)):
    try:
        user, token = await auth_service.login_doctor(db, body.code, body.phone_code, body.dev_phone)
        await db.commit()
    except PermissionError as e:
        await db.rollback()
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    return TokenOut(token=token, role=user.role, user_id=user.id)


@router.post("/admin/login", response_model=TokenOut)
async def admin_login(body: AdminLogin, db: AsyncSession = Depends(get_db)):
    """PC 运营后台登录：校验 staff 账号密码，返回真实角色令牌（角色以库为准，忽略入参 role）。"""
    staff = await staff_service.authenticate(db, body.username, body.password)
    if not staff:
        raise HTTPException(status_code=401, detail="账号或密码错误")
    token = create_token(sub=str(staff.id), role=staff.role)
    return TokenOut(token=token, role=staff.role, user_id=staff.id)


@router.get("/me", response_model=Me)
async def me(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    db_user = await db.get(User, int(user["sub"]))
    if not db_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    phone = decrypt(db_user.phone_enc) if db_user.phone_enc else None
    return Me(id=db_user.id, role=db_user.role, phone=mask_phone(phone) if phone else None)
