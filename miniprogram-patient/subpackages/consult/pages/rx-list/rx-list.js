const { request } = require('../../../../utils/request.js');

const AUDIT = { pending: '审核中', approved: '已通过', rejected: '已驳回' };

Page({
  data: { list: [] },

  onShow() {
    request('/prescriptions/mine').then((l) => {
      this.setData({
        list: (l || []).map((rx) => ({
          ...rx,
          auditText: AUDIT[rx.audit_status] || rx.audit_status,
          drugCount: (rx.items || []).length
        }))
      });
    }).catch(() => {});
  },

  open(e) {
    wx.navigateTo({ url: `/subpackages/consult/pages/prescription/prescription?orderId=${e.currentTarget.dataset.order}` });
  }
});
