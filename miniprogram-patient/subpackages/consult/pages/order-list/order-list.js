const { request } = require('../../../../utils/request.js');

const TEXT = { 0: '待支付', 1: '待接诊', 2: '问诊中', 3: '审核中', 4: '待重开', 5: '待付药费', 6: '已完成', 7: '已退款', 9: '已取消' };

// ISO 时间 → "YYYY-MM-DD HH:MM"
function fmtTime(s) { return s ? String(s).replace('T', ' ').slice(0, 16) : ''; }

Page({
  data: { status: '', list: [] },

  onLoad(q) {
    this.status = q.status || '';
    if (q.title) wx.setNavigationBarTitle({ title: q.title });
    this.load();
  },
  onShow() { this.load(); },

  load() {
    const url = '/orders/mine' + (this.status ? ('?status=' + this.status) : '');
    request(url).then((l) => {
      this.setData({
        list: (l || []).map((o) => ({
          ...o,
          statusText: TEXT[o.status] || '',
          typeText: o.consult_type === 'text' ? '图文' : '视频',
          feeYuan: (o.register_fee_fen / 100).toFixed(2),
          timeText: fmtTime(o.created_at),
          canEvaluate: o.status === 6 || o.status === 7   // 完成/退款后可评价（监管 2.4.1）
        }))
      });
    }).catch(() => {});
  },

  // 去评价（catchtap 防止触发卡片 open）
  goEvaluate(e) {
    const o = this.data.list[+e.currentTarget.dataset.i];
    if (!o) return;
    wx.navigateTo({ url: `/subpackages/consult/pages/evaluate/evaluate?orderId=${o.id}&doctor=${o.doctor_name || ''}` });
  },

  open(e) {
    const o = this.data.list[+e.currentTarget.dataset.i];
    if (!o) return;
    if (o.consult_type === 'text' && (o.status === 1 || o.status === 2)) {
      wx.navigateTo({ url: `/subpackages/consult/pages/chat/chat?orderId=${o.id}&peer=${o.doctor_name || '医生'}` });
    } else if (o.status === 2) {
      wx.navigateTo({ url: `/subpackages/consult/pages/video-room/video-room?room=${o.room_id || ('room_' + o.id)}` });
    } else if (o.status >= 3 && o.status <= 6) {
      wx.navigateTo({ url: `/subpackages/consult/pages/prescription/prescription?orderId=${o.id}` });
    } else if (o.status === 1) {
      wx.showToast({ title: '请耐心等待医生接诊', icon: 'none' });
    } else {
      wx.showToast({ title: TEXT[o.status] || '', icon: 'none' });
    }
  }
});
