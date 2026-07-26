const app = getApp();
const { request } = require('../../utils/request.js');

Page({
  data: {
    statusBar: 20,
    queueBar: '',
    currentPatient: { name: '' },
    quickServices: [
      { icon: 'payments', t: '待付药费', url: '/subpackages/consult/pages/order-list/order-list?status=5&title=待付药费' },
      { icon: 'medication', t: '我的处方', url: '/subpackages/consult/pages/rx-list/rx-list' },
      { icon: 'folder_shared', t: '电子病历', url: '/subpackages/consult/pages/record-list/record-list' }
    ],
    doctors: []
  },

  onLoad() {
    const info = wx.getWindowInfo ? wx.getWindowInfo() : wx.getSystemInfoSync();
    this.setData({ statusBar: info.statusBarHeight || 20 });
    const p = app.globalData.currentPatient;
    if (p) this.setData({ currentPatient: p });
  },

  onShow() {
    this.loadDoctors();
    const p = app.globalData.currentPatient;
    if (p) this.setData({ currentPatient: p });
    if (!app.globalData.token) { this.setData({ queueBar: '' }); return; }
    app.connectSignaling(); // 兜底：确保信令长连接已建立（接收 CALL_INVITE）
    request('/orders/active').then((r) => {
      this.setData({ queueBar: r && r.has ? `您有正在排队的视频问诊（${r.doctor_name || ''}），请保持手机亮屏` : '' });
    }).catch(() => {});
  },

  // 出诊医生（从后端动态加载，新增医生自动展示）
  loadDoctors() {
    request('/doctors', { auth: false }).then((list) => {
      const doctors = (Array.isArray(list) ? list : []).map((d) => ({
        id: d.id, name: d.name, dept: d.dept, title: d.title
      }));
      this.setData({ doctors });
    }).catch(() => {});
  },

  goQuick(e) {
    const url = e.currentTarget.dataset.url;
    if (url) wx.navigateTo({ url });
  },
  goSearch() { wx.navigateTo({ url: '/pages/search/search' }); },
  goRegister() { wx.switchTab({ url: '/pages/register/register' }); },
  goDoctor(e) {
    wx.navigateTo({ url: `/subpackages/consult/pages/doctor-detail/doctor-detail?id=${e.currentTarget.dataset.id}` });
  },
  onSwitchPatient() { wx.navigateTo({ url: '/pages/patients/patients' }); }
});
