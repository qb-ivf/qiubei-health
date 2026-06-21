// 微信支付封装（步战术5）。页面3 挂号费 / 页面6 药费共用。
const app = getApp();

/**
 * 发起支付：① 后端下单拿五元组 → ② wx.requestPayment。
 * 阶段二先 mock 流程，阶段三把 wx.request 指向后端 /api/pay/unifiedorder。
 * @returns {Promise<{ok:boolean, cancelled?:boolean}>}
 */
function requestPay(orderId) {
  return new Promise((resolve) => {
    wx.showLoading({ title: '正在下单...', mask: true });

    // —— 阶段三联调：取消下面的 mock，启用真实下单 ——
    // wx.request({
    //   url: app.globalData.baseUrl + '/api/pay/unifiedorder',
    //   method: 'POST',
    //   data: { orderId },
    //   header: { Authorization: 'Bearer ' + app.globalData.token },
    //   success: ({ data }) => {
    //     wx.hideLoading();
    //     wx.requestPayment({
    //       timeStamp: data.timeStamp, nonceStr: data.nonceStr,
    //       package: data.package, signType: data.signType, paySign: data.paySign,
    //       success: () => resolve({ ok: true }),
    //       fail: (err) => resolve({ ok: false, cancelled: err.errMsg.includes('cancel') })
    //     });
    //   },
    //   fail: () => { wx.hideLoading(); resolve({ ok: false }); }
    // });

    // —— mock：模拟下单 + 支付成功 ——
    setTimeout(() => {
      wx.hideLoading();
      resolve({ ok: true });
    }, 900);
  });
}

module.exports = { requestPay };
