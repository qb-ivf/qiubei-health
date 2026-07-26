const app = getApp();
const { request } = require('../../../../utils/request.js');

function fmtTime(s) {
  return s ? String(s).replace('T', ' ').slice(0, 16) : '';
}

Page({
  data: {
    orderId: '',
    loaded: false,
    record: {}
  },

  onLoad(query) {
    this.setData({ orderId: query.orderId || '' });
    this.load();
  },

  load() {
    if (!this.data.orderId) return;
    request(`/prescriptions/record/by-order/${this.data.orderId}`).then((record) => {
      this.setData({
        loaded: true,
        record: {
          ...record,
          timeText: fmtTime(record.updated_at || record.created_at)
        }
      });
    }).catch((err) => {
      wx.showToast({ title: (err && err.detail) || '病历加载失败', icon: 'none' });
    });
  },

  openPrescription() {
    wx.navigateTo({
      url: `/subpackages/consult/pages/prescription/prescription?orderId=${this.data.orderId}`
    });
  },

  viewPdf() {
    const url = app.globalData.baseUrl.replace(/\/$/, '')
      + `/api/v1/prescriptions/record/${this.data.orderId}/pdf`;
    wx.downloadFile({
      url,
      header: { Authorization: `Bearer ${app.globalData.token}` },
      success: (res) => {
        if (res.statusCode === 200) {
          wx.openDocument({
            filePath: res.tempFilePath,
            fileType: 'pdf',
            fail: () => wx.showToast({ title: '打开病历失败', icon: 'none' })
          });
        } else {
          wx.showToast({ title: '电子病历原件尚未就绪', icon: 'none' });
        }
      },
      fail: () => wx.showToast({ title: '病历下载失败', icon: 'none' })
    });
  }
});
