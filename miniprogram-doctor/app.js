// 医生端小程序入口（逑贝医生端）
const { ORDER_STATUS } = require('./utils/constants');
const signaling = require('./utils/signaling.js');

App({
  globalData: {
    token: null,            // 医生 JWT（role: doctor）
    doctor: null,           // 当前登录医生信息
    onDuty: false,          // 接诊状态开关（FRD 页面 D1）
    socketTask: null,       // 全局 WebSocket 实例
    baseUrl: 'https://api.qb-medical.cn',
    wsUrl: 'wss://api.qb-medical.cn/ws',
    ORDER_STATUS
  },

  onLaunch() {
    wx.loadFontFace({
      global: true,
      family: 'Material Symbols Outlined',
      source: 'url("https://cdn.jsdelivr.net/npm/material-symbols@0.14.0/material-symbols-outlined.woff2")',
      scopes: ['webview', 'native'],
      success: () => {},
      fail: (e) => console.warn('图标字体加载失败', e)
    });

    const token = wx.getStorageSync('token');
    if (token) this.globalData.token = token;
    if (this.globalData.token) signaling.connect();
  },

  connectSignaling() { signaling.connect(); },

  // 登录守卫 + 白名单（FRD §2.1：非认证执业医师一律拦截）
  ensureLogin() {
    if (this.globalData.token) return true;
    wx.navigateTo({ url: '/pages/login/login' });
    return false;
  },

  ensureMediaAuth() {
    return new Promise((resolve) => {
      wx.getSetting({
        success: (res) => {
          const cam = res.authSetting['scope.camera'];
          const rec = res.authSetting['scope.record'];
          resolve(cam !== false && rec !== false);
        },
        fail: () => resolve(false)
      });
    });
  }
});
