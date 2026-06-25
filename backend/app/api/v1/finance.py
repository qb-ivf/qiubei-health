"""财务接口（M6 分账流水；M8 医生钱包/提现）。"""
from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...models.ledger import Ledger
from ...models.withdrawal import Withdrawal
from ...services import finance_service
from ..deps import get_current_user, require_role

router = APIRouter(prefix="/finance", tags=["finance"])


@router.get("/ledger")
async def ledger(user=Depends(require_role("admin", "finance")), db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Ledger).order_by(Ledger.id.desc()))
    return [
        {
            "order_id": r.order_id,
            "total": r.total_fen / 100,
            "hospital": r.hospital_fen / 100,
            "doctor": r.doctor_fen / 100,
            "platform": r.platform_fen / 100,
        }
        for r in res.scalars().all()
    ]


@router.get("/wallet")
async def wallet(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """医生可提现余额（M8）。"""
    if user.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="仅医生可访问")
    bal = await finance_service.doctor_balance_fen(db)
    return {"balance": bal / 100}


@router.get("/my-withdrawals")
async def my_withdrawals(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """医生本人提现记录（收入明细）。"""
    if user.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="仅医生可访问")
    res = await db.execute(
        select(Withdrawal).where(Withdrawal.doctor_uid == int(user["sub"])).order_by(Withdrawal.id.desc())
    )
    status_text = {"pending": "审核中", "paid": "已到账", "rejected": "已驳回"}
    return [
        {"id": w.id, "amount": w.amount_fen / 100, "status": w.status, "status_text": status_text.get(w.status, w.status)}
        for w in res.scalars().all()
    ]


@router.post("/withdrawals")
async def request_withdrawal(amount: float = Body(embed=True), user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """医生发起提现（M8）→ 冻结余额，进 admin 审批。"""
    if user.get("role") != "doctor":
        raise HTTPException(status_code=403, detail="仅医生可提现")
    try:
        w = await finance_service.create_withdrawal(db, int(user["sub"]), user.get("sub"), int(round(amount * 100)))
        await db.commit()
    except finance_service.FinanceError as e:
        await db.rollback()
        raise HTTPException(status_code=409, detail=str(e))
    return {"id": w.id, "status": w.status}
