"""站内消息接口（M7，消息诊室）。"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.database import get_db
from ...services import notification_service
from ..deps import get_current_user_id

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    items = await notification_service.list_for(db, uid)
    return [
        {"id": n.id, "type": n.ntype, "title": n.title, "body": n.body, "read": n.read, "order_id": n.order_id}
        for n in items
    ]


@router.post("/read-all")
async def read_all(uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """一键全部已读。"""
    cleared = await notification_service.mark_all_read(db, uid)
    await db.commit()
    return {"cleared": cleared}


@router.post("/{notif_id}/read")
async def read_one(notif_id: int, uid: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """标记单条已读（打开消息时调用）。"""
    await notification_service.mark_read(db, uid, notif_id)
    await db.commit()
    return {"ok": True}
