"""图文咨询：订单内消息（文字/图片），自建 WebSocket 实时推送（复用 ws.manager）。"""
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...constants import OrderStatus, Signal
from ...core.database import get_db
from ...models.message import Message
from ...models.order import Order
from ...models.prescription import Prescription
from ...models.user import Doctor
from ...schemas.chat import MessageIn, MessageOut
from ...ws import manager
from ..deps import get_current_user

router = APIRouter(prefix="/orders", tags=["chat"])

UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads"  # backend/uploads
ALLOWED_EXT = {"jpg", "jpeg", "png", "gif", "webp"}
_WRITABLE_STATUSES = {int(OrderStatus.WAITING), int(OrderStatus.CONSULTING)}


async def _role_in_order(order: Order, user: dict, db: AsyncSession) -> str:
    """校验当前用户是该订单的患者或医生，返回其角色。"""
    uid = int(user["sub"])
    if user.get("role") == "patient" and order.user_id == uid:
        return "patient"
    if user.get("role") == "doctor":
        did = await db.scalar(select(Doctor.id).where(Doctor.user_id == uid))
        if did == order.doctor_id:
            return "doctor"
    raise HTTPException(status_code=403, detail="无权访问该会话")


async def _push_to_peer(order: Order, sender_role: str, msg: Message, db: AsyncSession) -> None:
    """把新消息推给会话另一方。"""
    if sender_role == "patient":
        target = await db.scalar(select(Doctor.user_id).where(Doctor.id == order.doctor_id))
    else:
        target = order.user_id
    if target:
        await manager.send(target, {
            "type": Signal.CHAT_MESSAGE,
            "orderId": order.id,
            "msg": {"id": msg.id, "sender_role": msg.sender_role, "type": msg.type, "content": msg.content},
        })


def _is_chat_writable(status: int) -> bool:
    return status in _WRITABLE_STATUSES


def _ensure_chat_writable(order: Order) -> None:
    if not _is_chat_writable(order.status):
        raise HTTPException(status_code=409, detail="本次问诊已结束，聊天记录已转为只读")


@router.get("/{order_id}/messages", response_model=list[MessageOut])
async def list_messages(order_id: int, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    await _role_in_order(order, user, db)
    res = await db.execute(select(Message).where(Message.order_id == order_id).order_by(Message.id.asc()))
    return res.scalars().all()


@router.get("/{order_id}/chat-state")
async def chat_state(
    order_id: int,
    user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """图文问诊状态：供两端切换只读、进入处方或电子病历。"""
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    await _role_in_order(order, user, db)
    res = await db.execute(select(Prescription).where(Prescription.order_id == order_id))
    record = res.scalars().first()
    return {
        "status": order.status,
        "writable": _is_chat_writable(order.status),
        "has_medical_record": record is not None,
        "has_prescription": bool(
            record and record.audit_status != "not_required" and record.items
        ),
    }


@router.post("/{order_id}/messages", response_model=MessageOut)
async def send_message(order_id: int, body: MessageIn, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    role = await _role_in_order(order, user, db)
    _ensure_chat_writable(order)
    content = (body.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="内容不能为空")
    msg = Message(order_id=order_id, sender_role=role, type="text", content=content[:1024])
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    await _push_to_peer(order, role, msg, db)
    return msg


@router.post("/{order_id}/messages/image", response_model=MessageOut)
async def send_image(order_id: int, file: UploadFile = File(...), user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    order = await db.get(Order, order_id)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    role = await _role_in_order(order, user, db)
    _ensure_chat_writable(order)
    ext = (file.filename or "").rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "jpg"
    if ext not in ALLOWED_EXT:
        ext = "jpg"
    data = await file.read()
    if len(data) > 8 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="图片不能超过 8MB")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{ext}"
    (UPLOAD_DIR / name).write_bytes(data)
    msg = Message(order_id=order_id, sender_role=role, type="image", content=f"/uploads/{name}")
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    await _push_to_peer(order, role, msg, db)
    return msg
