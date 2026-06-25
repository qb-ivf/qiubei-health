const app = getApp();
const { request } = require('../../utils/request.js');

Page({
  data: {
    balance: '0.00',
    doctor: { name: '', title: '', audit_status: '', fee_fen: 0 },
    authText: '',
    metrics: { done: 0, score: '—', praise: 0 },  // 真实统计接口接入前用占位 0/—
    manage: [
      { t: '排班管理', icon: 'calendar_month', color: 'var(--primary)', bg: 'rgba(0,86,196,.1)' },
      { t: '诊金设置', icon: 'payments', color: 'var(--secondary)', bg: 'rgba(0,108,70,.1)' },
      { t: '常用语/快捷回复', icon: 'chat_bubble', color: 'var(--tertiary)', bg: 'rgba(137,77,0,.1)' },
      { t: '我的资质', icon: 'badge', color: 'var(--on-surface-variant)', bg: 'var(--sc-highest)' }
    ]
  },

  onShow() { this.loadWallet(); this.loadProfile(); this.loadStats(); },

  // 真实累计接诊量
  loadStats() {
    if (!app.globalData.token) return;
    request('/doctors/stats').then((s) => this.setData({ 'metrics.done': s.consulted || 0 })).catch(() => {});
  },

  loadWallet() {
    if (!app.globalData.token) return;
    request('/finance/wallet').then((r) => {
      this.setData({ balance: (r.balance || 0).toFixed(2) });
    }).catch(() => {});
  },

  // 拉本人档案：工作台展示真实姓名/职称/认证状态
  loadProfile() {
    if (!app.globalData.token) return;
    request('/doctors/profile').then((p) => {
      if (!p) return;
      const map = { approved: '执业资格已认证', pending: '资质审核中', rejected: '资质审核未通过' };
      this.setData({
        doctor: { name: p.name || '医生', title: p.title || '', audit_status: p.audit_status || '', fee_fen: p.register_fee_fen || 0 },
        authText: map[p.audit_status] || ''
      });
    }).catch(() => {});
  },

  comingSoon() { wx.showToast({ title: '功能完善中，敬请期待', icon: 'none' }); },
  goRecords() { wx.navigateTo({ url: '/subpackages/consult/pages/order-list/order-list?title=接诊记录' }); },
  goFinance() { wx.navigateTo({ url: '/pages/finance/finance' }); },

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

  tapManage(e) {
    const t = e.currentTarget.dataset.t || '';
    if (t.indexOf('资质') > -1) {
      wx.navigateTo({ url: '/pages/qualification/qualification' });
    } else if (t.indexOf('排班') > -1) {
      wx.navigateTo({ url: '/pages/schedule/schedule' });
    } else if (t.indexOf('诊金') > -1) {
      this.editFee();
    } else if (t.indexOf('常用语') > -1) {
      wx.navigateTo({ url: '/pages/phrases/phrases' });
    } else {
      wx.showToast({ title: t + '（建设中）', icon: 'none' });
    }
  },

  // 诊金设置：弹窗输入挂号费（元），保存到后端
  editFee() {
    const cur = this.data.doctor.fee_fen ? (this.data.doctor.fee_fen / 100).toFixed(2) : '';
    wx.showModal({
      title: '诊金设置', editable: true, placeholderText: '挂号费（元），如 40', content: cur,
      confirmText: '保存', cancelText: '取消',
      success: (r) => {
        if (!r.confirm) return;
        const yuan = parseFloat(r.content);
        if (isNaN(yuan) || yuan < 0) { wx.showToast({ title: '金额无效', icon: 'none' }); return; }
        request('/doctors/fee', { method: 'POST', data: { fee_fen: Math.round(yuan * 100) } })
          .then((p) => { this.setData({ 'doctor.fee_fen': p.register_fee_fen }); wx.showToast({ title: '已保存', icon: 'success' }); })
          .catch((e) => wx.showToast({ title: (e && e.detail) || '保存失败', icon: 'none' }));
      }
    });
  },
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
