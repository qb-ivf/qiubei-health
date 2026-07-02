// 问诊评价（订单完成/退款后，一单一评；数据用于天津监管 2.4.1 上报）
const { request } = require('../../../../utils/request.js');

const SAT_TEXT = ['', '非常不满意', '不满意', '一般', '满意', '非常满意'];

Page({
  data: {
    orderId: null,
    doctorName: '',
    done: null,          // 已有评价（只读展示）
    satisfaction: 5,
    scoring: 10,
    content: '',
    complaints: '',
    satText: SAT_TEXT[5],
    SAT_TEXT
  },

  onLoad(query) {
    this.setData({ orderId: +query.orderId, doctorName: query.doctor || '' });
    request(`/orders/${query.orderId}/evaluation`).then((ev) => {
      if (ev) this.setData({ done: { ...ev, satText: SAT_TEXT[ev.satisfaction] || '' } });
    }).catch(() => {});
  },

  pickStar(e) {
    const v = +e.currentTarget.dataset.v;
    this.setData({ satisfaction: v, satText: SAT_TEXT[v] });
  },
  onScore(e) { this.setData({ scoring: +e.detail.value }); },
  onContent(e) { this.setData({ content: e.detail.value }); },
  onComplaints(e) { this.setData({ complaints: e.detail.value }); },

  submit() {
    if (!this.data.content.trim()) { wx.showToast({ title: '请写几句评价内容', icon: 'none' }); return; }
    request(`/orders/${this.data.orderId}/evaluation`, {
      method: 'POST',
      data: {
        satisfaction: this.data.satisfaction,
        scoring: this.data.scoring,
        content: this.data.content.trim(),
        complaints: this.data.complaints.trim() || null
      }
    }).then((ev) => {
      wx.showToast({ title: '感谢您的评价', icon: 'success', duration: 1200 });
      this.setData({ done: { ...ev, satText: SAT_TEXT[ev.satisfaction] || '' } });
      setTimeout(() => wx.navigateBack(), 1200);
    }).catch((e) => {
      wx.showToast({ title: (e && e.detail) || '提交失败', icon: 'none' });
    });
  }
});
