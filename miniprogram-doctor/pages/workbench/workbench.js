const app = getApp();
const { request } = require('../../utils/request.js');

Page({
  data: {
    balance: '0.00',
    doctor: { name: '张大夫', title: '主任医师' },
    manage: [
      { t: '排班管理', icon: 'calendar_month', color: 'var(--primary)', bg: 'rgba(0,86,196,.1)' },
      { t: '诊金设置', icon: 'payments', color: 'var(--secondary)', bg: 'rgba(0,108,70,.1)' },
      { t: '常用语/快捷回复', icon: 'chat_bubble', color: 'var(--tertiary)', bg: 'rgba(137,77,0,.1)' },
      { t: '多点执业/资质管理', icon: 'badge', color: 'var(--on-surface-variant)', bg: 'var(--sc-highest)' }
    ]
  },

  onShow() { this.loadWallet(); },

  loadWallet() {
    if (!app.globalData.token) return;
    request('/finance/wallet').then((r) => {
      this.setData({ balance: (r.balance || 0).toFixed(2) });
    }).catch(() => {});
  },

  // 发起提现 → 冻结余额 → 进 PC 后台财务审批
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
          this.loadWallet();
        }).catch((err) => wx.showToast({ title: (err && err.detail) || '提现失败', icon: 'none' }));
      }
    });
  },

  tapManage(e) { wx.showToast({ title: e.currentTarget.dataset.t, icon: 'none' }); },
  logout() {
    wx.showModal({
      title: '退出登录', content: '确认退出当前账号？',
      success: (r) => {
        if (r.confirm) {
          app.globalData.token = null;
          wx.removeStorageSync('token');
          wx.reLaunch({ url: '/pages/login/login' });
        }
      }
    });
  }
});
