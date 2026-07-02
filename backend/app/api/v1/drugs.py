"""院内药品搜索（医生端开方选药；替代小程序内置演示药品库）。

返回 drug_id 供处方明细关联药品字典（监管处方接口 drcode 需与药品目录 hospDrcode 一致）。
特殊限售药一并返回并带 restricted 标记（前端置灰提示；后端提交时仍强制拦截）。
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...models.drug import Drug
from ..deps import get_current_user_id

router = APIRouter(prefix="/drugs", tags=["drugs"])


@router.get("")
async def search(
    q: str = Query("", max_length=50),
    limit: int = Query(20, ge=1, le=50),
    uid: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Drug).where(Drug.use_flag == "1")
    if q.strip():
        kw = f"%{q.strip()}%"
        stmt = stmt.where(or_(Drug.name.like(kw), Drug.spec.like(kw)))
    res = await db.execute(stmt.order_by(Drug.id.asc()).limit(limit))
    return [
        {"id": d.id, "name": d.name, "spec": d.spec, "price_fen": d.price_fen,
         "packing": d.packing, "restricted": d.restricted}
        for d in res.scalars().all()
    ]
