// 患者端小程序入口（逑贝健康）
const { ORDER_STATUS } = require('./utils/constants');
const signaling = require('./utils/signaling.js');

App({
  globalData: {
    token: null,            // 登录后由后端下发的 JWT
    userInfo: null,         // 微信用户信息
    currentPatient: null,   // 当前默认就诊人
    patients: [],           // 就诊人列表
    socketTask: null,       // 全局 WebSocket 实例
    consentSigned: false,   // 是否已签署知情同意（FRD §2.3）
    baseUrl: 'https://api.qb-medical.cn',          // 后端基址，阶段三联调改为局域网 IP
    wsUrl: 'ws://api.qb-medical.cn/ws',           // 信令长连接
    ORDER_STATUS
  },

  onLaunch() {
    // 全局加载 Material Symbols 图标字体（设计稿图标体系）
    // 注：dev 需勾选「不校验合法域名」或将 cdn.jsdelivr.net 加入 downloadFile 合法域名
    wx.loadFontFace({
      global: true,
      family: 'Material Symbols Outlined',
      source: 'url("https://cdn.jsdelivr.net/npm/material-symbols@0.14.0/material-symbols-outlined.woff2")',
      scopes: ['webview', 'native'],
      success: () => {},
      fail: (e) => console.warn('图标字体加载失败，可在 app.js 更新字体源', e)
    });

    // 读取本地 Token
    const token = wx.getStorageSync('token');
    if (token) this.globalData.token = token;
    const patient = wx.getStorageSync('currentPatient');
    if (patient) this.globalData.currentPatient = patient;
    if (wx.getStorageSync('consentSigned')) this.globalData.consentSigned = true;

    // 已登录则建立全局信令长连接（接收 CALL_INVITE 呼叫）
    if (this.globalData.token) signaling.connect();
  },

  // 登录成功后调用，建立信令连接
  connectSignaling() { signaling.connect(); },

  /**
   * 全局登录路由守卫（FRD §1.2）。受保护页 onLoad 调用：
   *   if (!getApp().ensureLogin()) return;
   */
  ensureLogin() {
    if (this.globalData.token) return true;
    wx.navigateTo({ url: '/pages/login/login' });
    return false;
  },

  /**
   * 准入闸门：支付/问诊前校验「实名 + 知情同意」（FRD §二）。
   */
  ensureConsent() {
    if (this.globalData.consentSigned) return true;
    wx.showModal({
      title: '互联网诊疗知情同意',
      content: '问诊前需阅读并同意《互联网诊疗知情同意书》《隐私政策》《医疗风险告知》。',
      confirmText: '同意签署',
      cancelText: '取消',
      success: (res) => {
        if (res.confirm) {
          this.globalData.consentSigned = true;
          wx.setStorageSync('consentSigned', true);
          // 存证到后端（best-effort）
          if (this.globalData.token) {
            wx.request({
              url: this.globalData.baseUrl.replace(/\/$/, '') + '/api/v1/consents',
              method: 'POST',
              header: { 'content-type': 'application/json', Authorization: 'Bearer ' + this.globalData.token },
              data: { consent_type: 'diagnosis', version: 'v1' }
            });
          }
        }
      }
    });
    return false;
  },

  /**
   * 音视频权限校验（进入页面 4/5 前）。
   */
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
