const { request } = require('../../../../utils/request.js');

function fmtTime(s) {
  return s ? String(s).replace('T', ' ').slice(0, 16) : '';
}

Page({
  data: { list: [] },

  onShow() {
    request('/prescriptions/records/mine').then((list) => {
      this.setData({
        list: (list || []).map((record) => ({
          ...record,
          timeText: fmtTime(record.updated_at || record.created_at),
          typeText: record.has_prescription ? '含电子处方' : '本次未开药'
        }))
      });
    }).catch((err) => {
      wx.showToast({ title: (err && err.detail) || '病历加载失败', icon: 'none' });
    });
  },

  open(e) {
    wx.navigateTo({
      url: `/subpackages/consult/pages/medical-record/medical-record?orderId=${e.currentTarget.dataset.order}`
    });
  }
});
