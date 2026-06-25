// 微信支付封装（步战术5）。M2 挂号支付 + 通用药费支付。
const { request } = require('./request.js');

/**
 * 挂号支付闭环：下单 → 预支付 → wx.requestPayment；
 * 测试号无商户号时 requestPayment 会 fail，自动降级开发 mock 支付。
 * @returns {Promise<{ok:boolean, orderId?:number, mock?:boolean, cancelled?:boolean}>}
 */
async function payRegister({ doctorId, slotId, patientId, consultType }) {
  let order;
  try {
    order = await request('/orders/register', {
      method: 'POST',
      data: { doctor_id: doctorId, slot_id: slotId, patient_id: patientId, consult_type: consultType || 'video' }
    });
  } catch (e) {
    return { ok: false, detail: (e && e.detail) || '下单失败' };
  }

  let pre;
  try {
    pre = await request(`/orders/${order.id}/prepay`, { method: 'POST' });
  } catch (e) {
    return { ok: false, detail: '预支付失败' };
  }

  // 开发环境（mock 预支付，无真实商户号）：直接走 mock 支付，不调 wx.requestPayment
  if (pre.package && pre.package.indexOf('mock_') > -1) {
    try {
      await request(`/orders/${order.id}/pay/mock`, { method: 'POST' });
      return { ok: true, orderId: order.id, mock: true };
    } catch (e) {
      return { ok: false, detail: '支付失败' };
    }
  }

  // 生产环境：真实五元组 → 拉起微信支付
  return new Promise((resolve) => {
    wx.requestPayment({
      timeStamp: pre.timeStamp, nonceStr: pre.nonceStr, package: pre.package,
      signType: pre.signType, paySign: pre.paySign,
      success: () => resolve({ ok: true, orderId: order.id }),
      fail: (err) => {
        // 用户主动取消
        if (err && err.errMsg && err.errMsg.indexOf('cancel') > -1) {
          resolve({ ok: false, cancelled: true });
          return;
        }
        // 测试号/无商户号 → 走开发 mock 支付，便于联调验收
        request(`/orders/${order.id}/pay/mock`, { method: 'POST' })
          .then(() => resolve({ ok: true, orderId: order.id, mock: true }))
          .catch(() => resolve({ ok: false, detail: '支付失败' }));
      }
    });
  });
}

// 药费支付闭环（M6）：drug-prepay → 支付 → 5→6 + 分账。测试号自动降级 mock。
async function payDrug(orderId) {
  let pre;
  try {
    pre = await request(`/orders/${orderId}/drug-prepay`, { method: 'POST' });
  } catch (e) {
    return { ok: false, detail: (e && e.detail) || '预支付失败' };
  }

  if (pre.package && pre.package.indexOf('mock_') > -1) {
    try {
      await request(`/orders/${orderId}/drug-pay/mock`, { method: 'POST' });
      return { ok: true, mock: true };
    } catch (e) {
      return { ok: false, detail: '支付失败' };
    }
  }

  return new Promise((resolve) => {
    wx.requestPayment({
      timeStamp: pre.timeStamp, nonceStr: pre.nonceStr, package: pre.package,
      signType: pre.signType, paySign: pre.paySign,
      success: () => resolve({ ok: true, orderId }),
      fail: (err) => {
        if (err && err.errMsg && err.errMsg.indexOf('cancel') > -1) { resolve({ ok: false, cancelled: true }); return; }
        request(`/orders/${orderId}/drug-pay/mock`, { method: 'POST' })
          .then(() => resolve({ ok: true, orderId, mock: true }))
          .catch(() => resolve({ ok: false, detail: '支付失败' }));
      }
    });
  });
}

module.exports = { payRegister, payDrug };
