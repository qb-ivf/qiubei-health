"""操作审计日志服务。record() 仅 add，不 commit，由调用方随业务一起提交。"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.audit_log import AuditLog
from ..models.staff import Staff


async def record(
    db: AsyncSession, user: dict, request, action: str,
    target_type: str | None = None, target_id=None, detail: str | None = None,
) -> None:
    """记录一条审计日志。user 为 JWT 载荷（sub/role），request 用于取 IP。"""
    actor_id = int(user["sub"]) if user.get("sub") else 0
    name = None
    staff = await db.get(Staff, actor_id)
    if staff:
        name = staff.name or staff.username
    ip = request.client.host if request and request.client else None
    db.add(AuditLog(
        actor_id=actor_id, actor_name=name, actor_role=user.get("role"),
        action=action, target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        detail=detail, ip=ip,
    ))


async def query(
    db: AsyncSession, action: str | None = None, actor: str | None = None, limit: int = 300,
) -> list[AuditLog]:
    q = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if action:
        q = q.where(AuditLog.action == action)
    if actor:
        q = q.where(AuditLog.actor_name.like(f"%{actor}%"))
    res = await db.execute(q)
    return list(res.scalars().all())
