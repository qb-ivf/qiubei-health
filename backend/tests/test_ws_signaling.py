"""客户端只能发送通话信令，不能伪造处方或病历完成结果。"""
import pytest

from app.constants import Signal
from app import ws


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
