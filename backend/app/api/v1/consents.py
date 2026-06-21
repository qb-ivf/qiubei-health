"""知情同意接口（M1，FRD §2.3）。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...models.user import Consent
from ...schemas.patient import ConsentIn
from ..deps import get_current_user_id

router = APIRouter(prefix="/consents", tags=["consents"])


@router.post("")
async def sign(body: ConsentIn, uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    db.add(Consent(user_id=uid, consent_type=body.consent_type, version=body.version))
    await db.commit()
    return {"code": 0, "signed": True}


@router.get("/status")
async def status(uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Consent).where(Consent.user_id == uid))
    return {"signed": res.scalars().first() is not None}
