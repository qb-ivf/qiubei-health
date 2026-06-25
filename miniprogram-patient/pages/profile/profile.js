const app = getApp();
const { request } = require('../../utils/request.js');

Page({
  data: {
    user: { name: '王小明', idMask: '310***********1234' },
    orders: [
      { t: '待接诊', icon: 'pending_actions', s: 1, badge: 0 },
      { t: '问诊中', icon: 'chat_bubble', s: 2 },
      { t: '已完成', icon: 'task_alt', s: 6 },
      { t: '退款/申诉', icon: 'payments', s: 7 }
    ],
    assets: [
      { t: '我的处方', icon: 'prescriptions', color: 'var(--primary)', bg: 'rgba(0,86,196,.1)' },
      { t: '报告单查询', icon: 'lab_research', color: 'var(--secondary)', bg: 'rgba(0,108,70,.1)' },
      { t: '挂号预约记录', icon: 'calendar_month', color: 'var(--tertiary)', bg: 'rgba(137,77,0,.1)' },
      { t: '电子病历档案', icon: 'clinical_notes', color: 'var(--primary)', bg: 'rgba(0,86,196,.1)' }
    ]
  },

  onShow() {
    const p = app.globalData.currentPatient;
    if (p) this.setData({ user: { name: p.name, idMask: p.idMask || '310***********1234' } });
    if (!app.globalData.token) return;
    // 待接诊角标用真实数
    request('/orders/mine?status=1').then((l) => {
      const n = (l || []).length;
      this.setData({ orders: this.data.orders.map((o) => (o.s === 1 ? { ...o, badge: n } : o)) });
    }).catch(() => {});
  },

  goPatients() { wx.navigateTo({ url: '/pages/patients/patients' }); },

  // 我的问诊：按状态进订单列表
  goOrders(e) {
    const s = e.currentTarget.dataset.s;
    const t = e.currentTarget.dataset.t || '我的问诊';
    const q = s ? `?status=${s}&title=${t}` : '';
    wx.navigateTo({ url: `/subpackages/consult/pages/order-list/order-list${q}` });
  },

  // 健康资产：我的处方 → 处方列表，其余暂占位
  goAsset(e) {
    const t = e.currentTarget.dataset.t;
    if (t === '我的处方') {
      wx.navigateTo({ url: '/subpackages/consult/pages/rx-list/rx-list' });
    } else {
      wx.showToast({ title: '功能完善中，敬请期待', icon: 'none' });
    }
  }
});
