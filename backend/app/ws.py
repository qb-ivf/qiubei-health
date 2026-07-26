"""WebSocket 信令中心（PRD §2.2）。

本机连接保存在内存，跨进程/跨实例消息、在线状态和房间映射通过 Redis 协调。
连接：ws://host/ws?token=<JWT>。消息为 JSON：{type, ...}。
"""
import asyncio
import json
import logging
import time
import uuid

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from .constants import Signal
from .core.redis import redis_client
from .core.security import decode_token

logger = logging.getLogger("ws")
router = APIRouter()
_SIGNAL_CHANNEL = "ws:signals:v1"
_PRESENCE_TTL_SECONDS = 90
_ROOM_TTL_SECONDS = 24 * 60 * 60


class ConnectionManager:
    def __init__(self):
        self.active: dict[int, WebSocket] = {}  # uid -> ws
        self.instance_id = uuid.uuid4().hex
        self._tasks: list[asyncio.Task] = []
        self._running = False

    async def connect(self, uid: int, ws: WebSocket):
        await ws.accept()
        previous = self.active.get(uid)
        if previous is not None and previous is not ws:
            try:
                await previous.close(code=4000, reason="账号已在新连接上线")
            except Exception:  # noqa: BLE001
                pass
        self.active[uid] = ws
        await self._refresh_presence(uid)

    async def disconnect(self, uid: int, ws: WebSocket | None = None):
        if ws is not None and self.active.get(uid) is not ws:
            return
        self.active.pop(uid, None)
        try:
            await redis_client.zrem(self._presence_key(uid), self.instance_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ws 清理在线状态失败 uid=%s: %s", uid, exc)

    @staticmethod
    def _presence_key(uid: int) -> str:
        return f"ws:online:{uid}"

    async def _refresh_presence(self, uid: int) -> None:
        now = int(time.time())
        key = self._presence_key(uid)
        try:
            pipe = redis_client.pipeline()
            pipe.zadd(key, {self.instance_id: now + _PRESENCE_TTL_SECONDS})
            pipe.expire(key, _PRESENCE_TTL_SECONDS * 2)
            await pipe.execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("ws 更新在线状态失败 uid=%s: %s", uid, exc)

    async def is_online(self, uid: int) -> bool:
        if uid in self.active:
            return True
        key = self._presence_key(uid)
        try:
            now = int(time.time())
            pipe = redis_client.pipeline()
            pipe.zremrangebyscore(key, "-inf", now)
            pipe.zcard(key)
            _, count = await pipe.execute()
            return bool(count)
        except Exception as exc:  # noqa: BLE001
            logger.warning("ws 查询在线状态失败 uid=%s: %s", uid, exc)
            return False

    async def _send_local(self, uid: int, message: dict) -> bool:
        ws = self.active.get(uid)
        if not ws:
            return False
        try:
            await ws.send_text(json.dumps(message, ensure_ascii=False))
            return True
        except Exception:  # noqa: BLE001
            await self.disconnect(uid, ws)
            return False

    async def send(self, uid: int, message: dict) -> bool:
        local_sent = await self._send_local(uid, message)
        if not self._running:
            return local_sent
        envelope = {
            "source": self.instance_id,
            "uid": uid,
            "message": message,
        }
        try:
            await redis_client.publish(
                _SIGNAL_CHANNEL,
                json.dumps(envelope, ensure_ascii=False, separators=(",", ":")),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("ws 跨实例发布失败 uid=%s: %s", uid, exc)
            return local_sent
        return local_sent or await self.is_online(uid)

    async def set_room(self, room_id: str, patient_uid: int, doctor_uid: int) -> None:
        room = {"patient": patient_uid, "doctor": doctor_uid}
        rooms[room_id] = room
        try:
            await redis_client.set(
                f"ws:room:{room_id}",
                json.dumps(room, separators=(",", ":")),
                ex=_ROOM_TTL_SECONDS,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("ws 房间写入 Redis 失败 room=%s: %s", room_id, exc)

    async def get_room(self, room_id: str) -> dict | None:
        room = rooms.get(room_id)
        if room:
            return room
        try:
            raw = await redis_client.get(f"ws:room:{room_id}")
            if not raw:
                return None
            room = json.loads(raw)
            if not isinstance(room, dict) or "patient" not in room or "doctor" not in room:
                return None
            rooms[room_id] = room
            return room
        except Exception as exc:  # noqa: BLE001
            logger.warning("ws 房间读取 Redis 失败 room=%s: %s", room_id, exc)
            return None

    async def delete_room(self, room_id: str) -> None:
        rooms.pop(room_id, None)
        try:
            await redis_client.delete(f"ws:room:{room_id}")
        except Exception as exc:  # noqa: BLE001
            logger.warning("ws 房间清理 Redis 失败 room=%s: %s", room_id, exc)

    async def _listen(self) -> None:
        while self._running:
            try:
                async with redis_client.pubsub() as pubsub:
                    await pubsub.subscribe(_SIGNAL_CHANNEL)
                    async for event in pubsub.listen():
                        if not self._running:
                            return
                        if event.get("type") != "message":
                            continue
                        try:
                            envelope = json.loads(event["data"])
                            if envelope.get("source") == self.instance_id:
                                continue
                            await self._send_local(int(envelope["uid"]), envelope["message"])
                        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                            logger.warning("ws 忽略非法 Redis 信令")
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                logger.warning("ws Redis 订阅中断，2 秒后重连: %s", exc)
                await asyncio.sleep(2)

    async def _presence_loop(self) -> None:
        while self._running:
            try:
                for uid in list(self.active):
                    await self._refresh_presence(uid)
            except asyncio.CancelledError:
                raise
            await asyncio.sleep(30)

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._tasks = [
            asyncio.create_task(self._listen(), name="ws-redis-listener"),
            asyncio.create_task(self._presence_loop(), name="ws-presence-refresh"),
        ]

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        for uid in list(self.active):
            await self.disconnect(uid)


manager = ConnectionManager()
rooms: dict[str, dict] = {}  # room_id -> {"patient": uid, "doctor": uid}


async def _handle(uid: int, data: dict):
    t = data.get("type")
    room_id = data.get("roomId")
    room = await manager.get_room(room_id) if room_id else None
    if room and uid not in {room["patient"], room["doctor"]}:
        logger.warning("ws 拒绝非房间成员信令 uid=%s room=%s type=%s", uid, room_id, t)
        return

    if t == "PING":
        await manager.send(uid, {"type": "PONG"})
    elif t == Signal.CALL_ANSWER and room and uid == room["patient"]:
        # 患者接听 → 通知医生开始推流
        await manager.send(room["doctor"], {"type": Signal.START_STREAM, "roomId": room_id})
    elif t == Signal.CALL_REJECT and room and uid == room["patient"]:
        await manager.send(room["doctor"], {"type": Signal.CALL_REJECT, "roomId": room_id})
    elif t == Signal.CALL_FINISHED and room:
        other = room["doctor"] if uid == room["patient"] else room["patient"]
        # 客户端只能中继“通话已挂断”；处方/病历结果由业务接口提交成功后服务端推送。
        await manager.send(
            other,
            {
                "type": Signal.CALL_FINISHED,
                "roomId": room_id,
                "result": "call_ended",
            },
        )


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
        await manager.disconnect(uid, websocket)
        logger.info("ws 断开 uid=%s", uid)
