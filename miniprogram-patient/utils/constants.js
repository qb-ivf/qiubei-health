// 全局常量：订单状态机 + WebSocket 信令（与后端严格对齐，FRD §1.3 / §三）
const ORDER_STATUS = {
  PENDING: 0,      // 待支付
  WAITING: 1,      // 候诊中
  CONSULTING: 2,   // 问诊中
  AUDITING: 3,     // 待药师审核
  REJECTED: 4,     // 处方被驳回
  PRESCRIBED: 5,   // 已开方/待付药费
  FINISHED: 6,     // 问诊完成
  REFUNDED: 7,     // 已退款
  CANCELLED: 9     // 已取消
};

const ORDER_STATUS_TEXT = {
  0: '待支付', 1: '候诊中', 2: '问诊中', 3: '审核中',
  4: '待重开', 5: '待付药费', 6: '已完成', 7: '已退款', 9: '已取消'
};

// WebSocket 信令类型（FRD 步战术3 信令状态机）
const SIGNAL = {
  INIT_CALL: 'INIT_CALL',
  CALL_INVITE: 'CALL_INVITE',
  CALL_REJECT: 'CALL_REJECT',
  CALL_ANSWER: 'CALL_ANSWER',
  CALL_FINISHED: 'CALL_FINISHED',
  CHAT_MESSAGE: 'CHAT_MESSAGE'
};

module.exports = { ORDER_STATUS, ORDER_STATUS_TEXT, SIGNAL };
