"""通知服务（M7）。落库站内消息 + 微信订阅消息下发（占位）。"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.notification import Notification


async def notify(db: AsyncSession, user_id: int, ntype: str, title: str, body: str = "", order_id: int | None = None):
    db.add(Notification(user_id=user_id, ntype=ntype, title=title, body=body, order_id=order_id))
    await db.flush()
    # TODO(M7+): 调微信订阅消息下发（需用户授权模板 + 正式主体）


async def list_for(db: AsyncSession, user_id: int) -> list[Notification]:
    res = await db.execute(
        select(Notification).where(Notification.user_id == user_id).order_by(Notification.id.desc())
    )
    return list(res.scalars().all())


async def mark_read(db: AsyncSession, user_id: int, notif_id: int) -> None:
    res = await db.execute(
        select(Notification).where(Notification.id == notif_id, Notification.user_id == user_id)
    )
    n = res.scalar_one_or_none()
    if n and not n.read:
        n.read = True
        await db.flush()


async def mark_all_read(db: AsyncSession, user_id: int) -> int:
    res = await db.execute(
        select(Notification).where(Notification.user_id == user_id, Notification.read.is_(False))
    )
    items = list(res.scalars().all())
    for n in items:
        n.read = True
    await db.flush()
    return len(items)
