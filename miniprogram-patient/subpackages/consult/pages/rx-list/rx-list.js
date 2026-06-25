const { request } = require('../../../../utils/request.js');

const AUDIT = { pending: '审核中', approved: '已通过', rejected: '已驳回' };

// ISO 时间 → "YYYY-MM-DD HH:MM"
function fmtTime(s) { return s ? String(s).replace('T', ' ').slice(0, 16) : ''; }

Page({
  data: { list: [] },

  onShow() {
    request('/prescriptions/mine').then((l) => {
      this.setData({
        list: (l || []).map((rx) => ({
          ...rx,
          auditText: AUDIT[rx.audit_status] || rx.audit_status,
          drugCount: (rx.items || []).length,
          timeText: fmtTime(rx.created_at)
        }))
      });
    }).catch(() => {});
  },

  open(e) {
    wx.navigateTo({ url: `/subpackages/consult/pages/prescription/prescription?orderId=${e.currentTarget.dataset.order}` });
  }
});
