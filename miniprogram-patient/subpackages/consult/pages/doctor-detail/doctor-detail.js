const app = getApp();
const { requestPay } = require('../../../../utils/pay.js');

Page({
  data: {
    service: 'video',
    agreed: false,
    doctor: { name: '张建设', title: '主任医师', good: '慢阻肺、哮喘、肺部感染等呼吸系统疾病诊治', years: 25 },
    patient: { name: '王小明', idMask: '320***********1234' }
  },

  onLoad(query) {
    if (query.id) this.doctorId = query.id;
    const p = app.globalData.currentPatient;
    if (p) this.setData({ patient: { name: p.name, idMask: p.idMask || '320***********1234' } });
  },

  selectService(e) { this.setData({ service: e.currentTarget.dataset.s }); },
  togglePolicy() { this.setData({ agreed: !this.data.agreed }); },
  switchPatient() { wx.navigateTo({ url: '/pages/patients/patients' }); },

  // 步战术5：挂号支付闭环
  async handlePay() {
    if (!this.data.agreed) {
      wx.showToast({ title: '请先勾选协议', icon: 'none' });
      return;
    }
    // 准入闸门：知情同意（FRD §2.3）
    if (!app.ensureConsent()) return;

    const res = await requestPay('REG_' + Date.now());
    if (res.ok) {
      // 支付成功 → Toast → switchTab 回首页（挂黄色排队提示条由首页读状态机渲染）
      wx.showToast({ title: '预约成功，正在安排诊室', icon: 'success', duration: 1500 });
      app.globalData.queueing = true;
      setTimeout(() => wx.switchTab({ url: '/pages/index/index' }), 1500);
    } else if (res.cancelled) {
      // 用户主动取消，静默
    } else {
      wx.showToast({ title: '支付失败，请重试', icon: 'none' });
    }
  }
});
