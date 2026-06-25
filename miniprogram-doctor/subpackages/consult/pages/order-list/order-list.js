const { request } = require('../../../../utils/request.js');

const TEXT = { 0: '待支付', 1: '待接诊', 2: '问诊中', 3: '审核中', 4: '待重开', 5: '已开方', 6: '已完成', 7: '已退款', 9: '已取消' };

Page({
  data: { status: '', list: [] },

  onLoad(q) {
    this.status = q.status || '';
    if (q.title) wx.setNavigationBarTitle({ title: q.title });
    this.load();
  },
  onShow() { this.load(); },

  load() {
    const url = '/orders/doctor-mine' + (this.status ? ('?status=' + this.status) : '');
    request(url).then((l) => {
      this.setData({
        list: (l || []).map((o) => ({
          ...o, statusText: TEXT[o.status] || '', typeText: o.consult_type === 'text' ? '图文' : '视频'
        }))
      });
    }).catch(() => {});
  },

  open(e) {
    const o = this.data.list[+e.currentTarget.dataset.i];
    if (!o) return;
    if (o.consult_type === 'text' && (o.status === 1 || o.status === 2)) {
      wx.navigateTo({ url: `/subpackages/consult/pages/chat/chat?orderId=${o.id}&peer=${o.patient_name || '患者'}` });
    } else if (o.status >= 2) {
      wx.navigateTo({ url: `/subpackages/consult/pages/prescribe/prescribe?order=${o.id}&tab=record` });
    } else {
      wx.showToast({ title: '请在接诊大厅接诊', icon: 'none' });
    }
  }
});
