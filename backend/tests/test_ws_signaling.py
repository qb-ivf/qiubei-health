"""客户端只能发送通话信令，不能伪造处方或病历完成结果。"""
import json

import pytest

from app.constants import Signal
from app import ws


class _Socket:
    def __init__(self):
        self.sent = []
        self.closed = []

    async def send_text(self, payload):
        self.sent.append(payload)

    async def close(self, **kwargs):
        self.closed.append(kwargs)


@pytest.mark.asyncio
async def test_client_cannot_forge_consultation_result(monkeypatch):
    sent = []

    async def fake_send(uid, message):
        sent.append((uid, message))
        return True

    monkeypatch.setattr(ws.manager, "send", fake_send)
    ws.rooms["room_test"] = {"patient": 11, "doctor": 22}
    try:
        await ws._handle(
            22,
            {
                "type": Signal.CALL_FINISHED,
                "roomId": "room_test",
                "result": "prescription",
                "orderId": 999,
            },
        )
    finally:
        ws.rooms.pop("room_test", None)

    assert sent == [
        (
            11,
            {
                "type": Signal.CALL_FINISHED,
                "roomId": "room_test",
                "result": "call_ended",
            },
        )
    ]


@pytest.mark.asyncio
async def test_non_member_cannot_send_room_signal(monkeypatch):
    sent = []

    async def fake_send(uid, message):
        sent.append((uid, message))
        return True

    monkeypatch.setattr(ws.manager, "send", fake_send)
    ws.rooms["room_test"] = {"patient": 11, "doctor": 22}
    try:
        await ws._handle(
            33,
            {"type": Signal.CALL_FINISHED, "roomId": "room_test"},
        )
    finally:
        ws.rooms.pop("room_test", None)

    assert sent == []


@pytest.mark.asyncio
async def test_manager_publishes_cross_instance_envelope(monkeypatch):
    published = []

    class _Redis:
        async def publish(self, channel, payload):
            published.append((channel, json.loads(payload)))

    manager = ws.ConnectionManager()
    socket = _Socket()
    manager.active[7] = socket
    manager._running = True
    monkeypatch.setattr(ws, "redis_client", _Redis())

    assert await manager.send(7, {"type": "QUEUE_UPDATE"}) is True
    assert json.loads(socket.sent[0]) == {"type": "QUEUE_UPDATE"}
    assert published[0][1] == {
        "source": manager.instance_id,
        "uid": 7,
        "message": {"type": "QUEUE_UPDATE"},
    }


@pytest.mark.asyncio
async def test_stale_socket_disconnect_cannot_remove_new_connection(monkeypatch):
    manager = ws.ConnectionManager()
    old_socket = _Socket()
    new_socket = _Socket()
    manager.active[7] = new_socket

    class _Redis:
        async def zrem(self, *args):
            raise AssertionError("旧连接不应清除新连接的在线状态")

    monkeypatch.setattr(ws, "redis_client", _Redis())
    await manager.disconnect(7, old_socket)
    assert manager.active[7] is new_socket
