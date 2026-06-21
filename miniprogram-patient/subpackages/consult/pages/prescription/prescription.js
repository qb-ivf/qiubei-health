const app = getApp();
const { requestPay } = require('../../../../utils/pay.js');

Page({
  data: {
    patient: { name: '王小明' },
    drugs: [
      { name: '阿莫西林胶囊 (Amoxicillin)', qty: '1 盒', spec: '0.25g * 24粒', usage: '口服，一次1粒，一日3次 (TID)' },
      { name: '布洛芬缓释胶囊 (Ibuprofen)', qty: '1 盒', spec: '0.3g * 22粒', usage: '口服，一次1粒，一日2次 (BID)，发热时服用' }
    ]
  },

  onLoad() {
    const p = app.globalData.currentPatient;
    if (p) this.setData({ patient: { name: p.name } });
  },

  // 步战术5：药费支付 → 成功后归档「待药房配送」→ 个人中心
  async payDrug() {
    const res = await requestPay('RX_' + Date.now());
    if (res.ok) {
      wx.showToast({ title: '支付成功，药品配送中', icon: 'success', duration: 1500 });
      setTimeout(() => wx.switchTab({ url: '/pages/profile/profile' }), 1500);
    } else if (!res.cancelled) {
      wx.showToast({ title: '支付失败，请重试', icon: 'none' });
    }
  }
});
