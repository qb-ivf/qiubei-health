"""全局常量：订单状态机 + 信令（与小程序端严格对齐，PRD §2.1）。"""
from enum import IntEnum


class OrderStatus(IntEnum):
    PENDING = 0      # 待支付
    WAITING = 1      # 候诊中/排队中
    CONSULTING = 2   # 问诊中/通话中
    AUDITING = 3     # 待药师审核处方
    REJECTED = 4     # 药师审核驳回
    PRESCRIBED = 5   # 药师审核通过/已开方
    FINISHED = 6     # 问诊完成
    REFUNDED = 7     # 已退款
    CANCELLED = 9    # 已取消


# 封闭式状态机：合法迁移白名单（PRD §2.1 核心流转逻辑），其余一律拒绝
ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.WAITING, OrderStatus.CANCELLED},
    OrderStatus.WAITING: {OrderStatus.CONSULTING, OrderStatus.REFUNDED},
    OrderStatus.CONSULTING: {OrderStatus.AUDITING, OrderStatus.FINISHED, OrderStatus.REFUNDED},
    OrderStatus.AUDITING: {OrderStatus.PRESCRIBED, OrderStatus.REJECTED},
    OrderStatus.REJECTED: {OrderStatus.AUDITING},
    OrderStatus.PRESCRIBED: {OrderStatus.FINISHED, OrderStatus.REFUNDED},
    OrderStatus.FINISHED: set(),
    OrderStatus.REFUNDED: set(),
    OrderStatus.CANCELLED: set(),
}


class Signal:
    """WebSocket 信令类型（PRD §2.2）。"""
    INIT_CALL = "INIT_CALL"
    CALL_INVITE = "CALL_INVITE"
    CALL_ANSWER = "CALL_ANSWER"
    CALL_REJECT = "CALL_REJECT"
    START_STREAM = "START_STREAM"
    CALL_FINISHED = "CALL_FINISHED"
    QUEUE_UPDATE = "QUEUE_UPDATE"   # 候诊队列变化（新患者支付入队）→ 通知医生刷新


class Role:
    PATIENT = "patient"
    DOCTOR = "doctor"
    PHARMACIST = "pharmacist"   # 审方药师
    ADMIN = "admin"             # 医院行政/运营
    FINANCE = "finance"         # 财务
