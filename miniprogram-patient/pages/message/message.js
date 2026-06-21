const app = getApp();
const { request } = require('../../utils/request.js');

const STYLE = {
  order: { icon: 'notifications', color: 'var(--tertiary)', bg: 'rgba(137,77,0,.1)' },
  rx: { icon: 'prescriptions', color: 'var(--primary)', bg: 'rgba(0,86,196,.1)' },
  logistics: { icon: 'local_shipping', color: 'var(--primary)', bg: 'rgba(0,86,196,.1)' },
  refund: { icon: 'payments', color: 'var(--error)', bg: 'rgba(186,26,26,.1)' },
  system: { icon: 'campaign', color: 'var(--secondary)', bg: 'rgba(0,108,70,.1)' }
};

Page({
  data: { sessions: [] },

  onShow() { this.load(); },

  load() {
    if (!app.globalData.token) { this.setData({ sessions: [] }); return; }
    request('/notifications').then((list) => {
      const sessions = (list || []).map((n) => ({
        id: n.id, title: n.title, desc: n.body, time: '', type: n.type, orderId: n.order_id,
        unread: n.read ? 0 : 1, ...(STYLE[n.type] || STYLE.system)
      }));
      this.setData({ sessions });
    }).catch(() => {});
  },

  open(e) {
    const { order, type } = e.currentTarget.dataset;
    if (!order) return;
    if (type === 'logistics') {
      wx.navigateTo({ url: `/subpackages/consult/pages/order/order?orderId=${order}` });
    } else if (type === 'rx') {
      wx.navigateTo({ url: `/subpackages/consult/pages/prescription/prescription?orderId=${order}` });
    }
  }
});
