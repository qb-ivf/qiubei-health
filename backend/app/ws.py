"""WebSocket 信令中心（PRD §2.2）。

单进程内存连接管理（MVP）。多 worker/多实例时改用 Redis Pub/Sub。
连接：ws://host/ws?token=<JWT>。消息为 JSON：{type, ...}。
"""
import json
import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from .constants import Signal
from .core.security import decode_token

logger = logging.getLogger("ws")
router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.active: dict[int, WebSocket] = {}  # uid -> ws

    async def connect(self, uid: int, ws: WebSocket):
        await ws.accept()
        self.active[uid] = ws

    def disconnect(self, uid: int):
        self.active.pop(uid, None)

    async def send(self, uid: int, message: dict) -> bool:
        ws = self.active.get(uid)
        if not ws:
            return False
        try:
            await ws.send_text(json.dumps(message, ensure_ascii=False))
            return True
        except Exception:  # noqa: BLE001
            self.disconnect(uid)
            return False


manager = ConnectionManager()
rooms: dict[str, dict] = {}  # room_id -> {"patient": uid, "doctor": uid}


async def _handle(uid: int, data: dict):
    t = data.get("type")
    room_id = data.get("roomId")
    room = rooms.get(room_id) if room_id else None

    if t == "PING":
        await manager.send(uid, {"type": "PONG"})
    elif t == Signal.CALL_ANSWER and room:
        # 患者接听 → 通知医生开始推流
        await manager.send(room["doctor"], {"type": Signal.START_STREAM, "roomId": room_id})
    elif t == Signal.CALL_REJECT and room:
        await manager.send(room["doctor"], {"type": Signal.CALL_REJECT, "roomId": room_id})
    elif t == Signal.CALL_FINISHED and room:
        other = room["doctor"] if uid == room["patient"] else room["patient"]
        await manager.send(other, {"type": Signal.CALL_FINISHED, "roomId": room_id})


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket, token: str = Query(default="")):
    payload = decode_token(token)
    if not payload:
        await websocket.close(code=4001)
        return
    uid = int(payload["sub"])
    await manager.connect(uid, websocket)
    logger.info("ws 连接 uid=%s role=%s", uid, payload.get("role"))
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                data = json.loads(raw)
            except ValueError:
                continue
            await _handle(uid, data)
    except WebSocketDisconnect:
        manager.disconnect(uid)
        logger.info("ws 断开 uid=%s", uid)
