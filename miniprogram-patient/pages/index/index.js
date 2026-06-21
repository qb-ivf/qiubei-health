const app = getApp();
const { request } = require('../../utils/request.js');

Page({
  data: {
    statusBar: 20,
    queueBar: '',
    currentPatient: { name: '王小明' },
    quickServices: [
      { icon: 'payments', t: '门诊缴费' },
      { icon: 'analytics', t: '报告查询' },
      { icon: 'medication', t: '处方购药' },
      { icon: 'folder_shared', t: '健康档案' }
    ],
    doctors: [
      { id: 1, name: '张建国', dept: '内科', title: '主任医师' },
      { id: 2, name: '李晓梅', dept: '儿科', title: '副主任医师' },
      { id: 3, name: '王志强', dept: '外科', title: '专家教授' }
    ]
  },

  onLoad() {
    const info = wx.getWindowInfo ? wx.getWindowInfo() : wx.getSystemInfoSync();
    this.setData({ statusBar: info.statusBarHeight || 20 });
    const p = app.globalData.currentPatient;
    if (p) this.setData({ currentPatient: p });
  },

  onShow() {
    if (!app.globalData.token) { this.setData({ queueBar: '' }); return; }
    request('/orders/active').then((r) => {
      this.setData({ queueBar: r && r.has ? `您有正在排队的视频问诊（${r.doctor_name || ''}），请保持手机亮屏` : '' });
    }).catch(() => {});
  },

  goSearch() { wx.navigateTo({ url: '/pages/search/search' }); },
  goRegister() { wx.switchTab({ url: '/pages/register/register' }); },
  goDoctor(e) {
    wx.navigateTo({ url: `/subpackages/consult/pages/doctor-detail/doctor-detail?id=${e.currentTarget.dataset.id}` });
  },
  onSwitchPatient() { wx.navigateTo({ url: '/pages/patients/patients' }); }
});
