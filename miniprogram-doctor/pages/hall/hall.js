const app = getApp();
const { request } = require('../../utils/request.js');
const signaling = require('../../utils/signaling.js');

Page({
  data: {
    onDuty: false,
    doctor: { name: '', subtitle: '' },
    stats: { waiting: 0, done: 0, income: '0.00' },
    rejected: [],
    queue: []
  },

  onLoad() {
    if (!app.ensureLogin()) return; // 医生端登录守卫（FRD §2.1 白名单）
    this.setData({ onDuty: app.globalData.onDuty });
    signaling.connect();
    // 患者接听后医生收到 START_STREAM
    signaling.on(signaling.SIGNAL.START_STREAM, () => {
      wx.showToast({ title: '患者已接听', icon: 'success' });
    });
  },

  onShow() { this.loadProfile(); this.loadWallet(); this.loadQueue(); },

  onUnload() { signaling.off(signaling.SIGNAL.START_STREAM); },

  // 真实登录医生身份
  loadProfile() {
    if (!app.globalData.token) return;
    request('/doctors/profile').then((p) => {
      if (!p) return;
      const sub = [p.title, p.dept].filter(Boolean).join(' · ') || '请完善执业资料';
      this.setData({ doctor: { name: p.name || '医生', subtitle: sub } });
    }).catch(() => {});
  },

  // 真实余额
  loadWallet() {
    if (!app.globalData.token) return;
    request('/finance/wallet').then((r) => {
      this.setData({ 'stats.income': (r.balance || 0).toFixed(2) });
    }).catch(() => {});
  },

  loadQueue() {
    if (!app.globalData.token) return;
    request('/orders/queue').then((list) => {
      if (!Array.isArray(list)) return;
      const queue = list.map((q) => ({
        id: q.order_id, no: q.no, name: q.patient_name,
        gender: q.gender || '—', age: '—', type: '视频问诊',
        wait: q.wait_minutes,
        chief: '（候诊中，点击接诊查看主诉）'
      }));
      this.setData({ queue, 'stats.waiting': queue.length });
    }).catch(() => {});
  },

  toggleDuty(e) {
    const onDuty = e.detail.value;
    app.globalData.onDuty = onDuty;
    this.setData({ onDuty });
  },

  // 立即接诊 → 后端 accept（1→2 + 向患者推 CALL_INVITE）→ 进开方诊室
  accept(e) {
    if (!this.data.onDuty) { wx.showToast({ title: '请先开启接诊', icon: 'none' }); return; }
    const id = e.currentTarget.dataset.id;
    const patient = this.data.queue.find((q) => q.id === id);
    request(`/orders/${id}/accept`, { method: 'POST' }).then((res) => {
      wx.showToast({ title: res.invited ? '已呼叫患者' : '患者不在线，已接诊', icon: 'none' });
      wx.navigateTo({
        url: `/subpackages/consult/pages/prescribe/prescribe?room=${res.room_id}&name=${patient ? patient.name : ''}`
      });
    }).catch((err) => {
      wx.showToast({ title: (err && err.detail) || '接诊失败', icon: 'none' });
    });
  },

  reopen(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/subpackages/consult/pages/prescribe/prescribe?reopen=1&order=${id}&tab=prescription` });
  }
});
