const app = getApp();
const { payDrug } = require('../../../../utils/pay.js');
const { request } = require('../../../../utils/request.js');

const STATUS_TEXT = {
  pending: { title: '处方审核中', desc: '药师正在审核，请稍候' },
  approved: { title: '问诊已完成', desc: '感谢您的信任，请遵医嘱按时服药' },
  rejected: { title: '处方调整中', desc: '处方被退回，医生将重新开具' }
};

Page({
  data: {
    orderId: '',
    status: 'pending',
    statusTitle: '处方审核中',
    statusDesc: '药师正在审核，请稍候',
    patient: { name: '王小明' },
    diagnosis: '',
    drugs: [],
    drugFeeYuan: '0.00',
    doctorName: '',
    rejectReason: ''
  },

  onLoad(q) {
    this.setData({ orderId: q.orderId || '' });
    const p = app.globalData.currentPatient;
    if (p) this.setData({ 'patient.name': p.name });
    this.load();
  },

  onShow() { if (this.data.orderId) this.load(); }, // 重进可刷新审核状态

  load() {
    if (!this.data.orderId) return;
    request(`/prescriptions/by-order/${this.data.orderId}`).then((rx) => {
      const drugs = (rx.items || []).map((it) => ({
        name: it.name, qty: (it.qty || 1) + ' 盒', spec: it.spec, usage: it.usage
      }));
      const fee = (rx.items || []).reduce((s, it) => s + (it.price_fen || 0) * (it.qty || 1), 0);
      const t = STATUS_TEXT[rx.audit_status] || STATUS_TEXT.pending;
      this.setData({
        status: rx.audit_status,
        statusTitle: t.title,
        statusDesc: t.desc,
        diagnosis: rx.diagnosis || '',
        drugs,
        drugFeeYuan: (fee / 100).toFixed(2),
        doctorName: rx.doctor_name || '医生',
        rejectReason: rx.reject_reason || ''
      });
    }).catch(() => {});
  },

  // 药费支付（M6：5→6 + 分账）
  async payDrug() {
    if (this.data.status !== 'approved') {
      wx.showToast({ title: '处方审核中，暂不可支付', icon: 'none' });
      return;
    }
    const res = await payDrug(this.data.orderId);
    if (res.ok) {
      wx.showToast({ title: '支付成功，药品配送中', icon: 'success', duration: 1200 });
      setTimeout(() => wx.redirectTo({ url: `/subpackages/consult/pages/order/order?orderId=${this.data.orderId}` }), 1200);
    } else if (!res.cancelled) {
      wx.showToast({ title: res.detail || '支付失败', icon: 'none' });
    }
  },

  // 查看处方 PDF 原件（M9 reportlab 生成）
  viewPdf() {
    const url = app.globalData.baseUrl.replace(/\/$/, '') + '/api/v1/prescriptions/' + this.data.orderId + '/pdf';
    wx.downloadFile({
      url, header: { Authorization: 'Bearer ' + app.globalData.token },
      success: (res) => {
        if (res.statusCode === 200) {
          wx.openDocument({ filePath: res.tempFilePath, fileType: 'pdf', fail: () => wx.showToast({ title: '打开失败', icon: 'none' }) });
        } else {
          wx.showToast({ title: '获取失败', icon: 'none' });
        }
      },
      fail: () => wx.showToast({ title: '下载失败（检查域名校验）', icon: 'none' })
    });
  },

  // 申请退款（M7，仅未购药时）
  onRefund() {
    wx.showModal({
      title: '申请退款', content: '确认不购药并申请退款？', confirmText: '确认退款', cancelText: '取消',
      success: (r) => {
        if (!r.confirm) return;
        request(`/orders/${this.data.orderId}/refund`, { method: 'POST' }).then(() => {
          wx.showToast({ title: '已申请退款', icon: 'success' });
          setTimeout(() => wx.switchTab({ url: '/pages/index/index' }), 1200);
        }).catch((err) => wx.showToast({ title: (err && err.detail) || '退款失败', icon: 'none' }));
      }
    });
  }
});
