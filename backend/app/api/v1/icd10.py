"""ICD-10 诊断编码搜索（医生端开方诊断选择器，天津监管 S2）。"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...models.icd10 import Icd10Code
from ..deps import get_current_user_id

router = APIRouter(prefix="/icd10", tags=["icd10"])


@router.get("")
async def search(
    q: str = Query(min_length=1, max_length=50, description="编码前缀或名称关键词"),
    catalog: str = Query("west", pattern="^(west|tcm|all)$"),
    limit: int = Query(20, ge=1, le=50),
    uid: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """按编码前缀或名称模糊搜索，编码升序。返回 [{code, name}]。"""
    stmt = select(Icd10Code.code, Icd10Code.name).where(
        or_(Icd10Code.code.like(f"{q}%"), Icd10Code.name.like(f"%{q}%"))
    )
    if catalog != "all":
        stmt = stmt.where(Icd10Code.catalog == catalog)
    res = await db.execute(stmt.order_by(Icd10Code.code.asc()).limit(limit))
    return [{"code": c, "name": n} for c, n in res.all()]
