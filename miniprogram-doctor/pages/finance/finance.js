const app = getApp();
const { request } = require('../../utils/request.js');

Page({
  data: { balance: '0.00', list: [] },

  onShow() { this.load(); },

  load() {
    if (!app.globalData.token) return;
    request('/finance/wallet').then((r) => this.setData({ balance: (r.balance || 0).toFixed(2) })).catch(() => {});
    request('/finance/my-withdrawals').then((l) => this.setData({ list: l || [] })).catch(() => {});
  },

  withdraw() {
    wx.showModal({
      title: '提现', editable: true, placeholderText: '输入提现金额（元）',
      confirmText: '确认提现', cancelText: '取消',
      success: (res) => {
        if (!res.confirm) return;
        const amt = parseFloat(res.content);
        if (!amt || amt <= 0) { wx.showToast({ title: '金额无效', icon: 'none' }); return; }
        request('/finance/withdrawals', { method: 'POST', data: { amount: amt } }).then(() => {
          wx.showToast({ title: '提现申请已提交', icon: 'success' });
          this.load();
        }).catch((err) => wx.showToast({ title: (err && err.detail) || '提现失败', icon: 'none' }));
      }
    });
  }
});
