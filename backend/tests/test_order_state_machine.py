"""订单状态机纯逻辑测试（无需数据库即可运行：pytest）。"""
from app.constants import OrderStatus
from app.services.order_service import can_transition


def test_legal_transitions():
    assert can_transition(OrderStatus.PENDING, OrderStatus.WAITING)
    assert can_transition(OrderStatus.PENDING, OrderStatus.CANCELLED)
    assert can_transition(OrderStatus.WAITING, OrderStatus.CONSULTING)
    assert can_transition(OrderStatus.CONSULTING, OrderStatus.AUDITING)
    assert can_transition(OrderStatus.AUDITING, OrderStatus.PRESCRIBED)
    assert can_transition(OrderStatus.AUDITING, OrderStatus.REJECTED)
    assert can_transition(OrderStatus.REJECTED, OrderStatus.AUDITING)
    assert can_transition(OrderStatus.PRESCRIBED, OrderStatus.FINISHED)


def test_illegal_transitions():
    # 状态逆流 / 非法跳转一律拒绝
    assert not can_transition(OrderStatus.WAITING, OrderStatus.PENDING)
    assert not can_transition(OrderStatus.PENDING, OrderStatus.CONSULTING)
    assert not can_transition(OrderStatus.FINISHED, OrderStatus.AUDITING)
    assert not can_transition(OrderStatus.CANCELLED, OrderStatus.WAITING)


def test_terminal_states_have_no_exit():
    for terminal in (OrderStatus.FINISHED, OrderStatus.REFUNDED, OrderStatus.CANCELLED):
        assert all(not can_transition(terminal, to) for to in OrderStatus)
