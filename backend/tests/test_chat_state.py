"""图文问诊结束后必须只读，避免病历签署完成后继续改写问诊内容。"""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.chat import _ensure_chat_writable, _is_chat_writable
from app.constants import OrderStatus


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (OrderStatus.WAITING, True),
        (OrderStatus.CONSULTING, True),
        (OrderStatus.AUDITING, False),
        (OrderStatus.REJECTED, False),
        (OrderStatus.PRESCRIBED, False),
        (OrderStatus.FINISHED, False),
        (OrderStatus.REFUNDED, False),
        (OrderStatus.CANCELLED, False),
    ],
)
def test_chat_writable_statuses(status, expected):
    assert _is_chat_writable(int(status)) is expected


def test_finished_chat_rejects_new_messages():
    order = SimpleNamespace(status=int(OrderStatus.FINISHED))

    with pytest.raises(HTTPException) as exc:
        _ensure_chat_writable(order)

    assert exc.value.status_code == 409
    assert "只读" in exc.value.detail
