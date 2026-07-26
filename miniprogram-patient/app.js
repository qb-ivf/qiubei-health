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
    baseUrl: 'https://api.qb-medical.cn',          // 后端基址
    wsUrl: 'wss://api.qb-medical.cn/ws',           // 信令长连接（真机须 wss）
    ORDER_STATUS
  },

  onLaunch() {
    // 固定图标子集由本院 API 域名托管，不依赖第三方 CDN 或额外合法域名。
    wx.loadFontFace({
      global: true,
      family: 'Material Symbols Outlined',
      source: 'url("https://api.qb-medical.cn/static/material-symbols-outlined-subset.woff2?v=1912ddef")',
      scopes: ['webview', 'native'],
      success: () => {},
      fail: (e) => console.warn('本院图标字体加载失败，请检查 API 域名连通性', e)
    });

    // 读取本地 Token
    const token = wx.getStorageSync('token');
    if (token) this.globalData.token = token;
    const patient = wx.getStorageSync('currentPatient');
    if (patient) this.globalData.currentPatient = patient;

    // 已登录则建立全局信令长连接（接收 CALL_INVITE 呼叫）
    if (this.globalData.token) signaling.connect();
  },

  // 回到前台：重连信令 + 补偿错过的视频呼叫 + 同步默认就诊人
  onShow() {
    if (!this.globalData.token) return;
    signaling.connect();
    this.syncConsentStatus();
    this.tryRejoinConsult();
    this.loadDefaultPatient();
  },

  // 拉取并设置默认就诊人（真实数据，替代写死的"王小明"）
  loadDefaultPatient() {
    if (!this.globalData.token) return;
    wx.request({
      url: this.globalData.baseUrl.replace(/\/$/, '') + '/api/v1/patients',
      header: { 'content-type': 'application/json', Authorization: 'Bearer ' + this.globalData.token },
      success: ({ data }) => {
        const ps = Array.isArray(data) ? data : [];
        const def = ps.find((p) => p.is_default) || ps[0];
        if (def) {
          this.globalData.currentPatient = { id: def.id, name: def.name, idMask: def.id_card };
          wx.setStorageSync('currentPatient', this.globalData.currentPatient);
        }
      }
    });
  },

  // 登录成功后调用，建立信令连接
  connectSignaling() { signaling.connect(); },

  /**
   * 离线补偿：错过 CALL_INVITE 时，回前台查进行中订单并自动拉回接听页。
   * 解决"医生接诊瞬间患者不在线 → 收不到呼叫"的问题（信令无离线队列，见 pending #13）。
   */
  tryRejoinConsult() {
    if (!this.globalData.token) return;
    const pages = getCurrentPages();
    const cur = pages.length ? pages[pages.length - 1].route : '';
    if (cur.indexOf('consult/pages/call') > -1 || cur.indexOf('video-room') > -1) return; // 已在通话流程
    wx.request({
      url: this.globalData.baseUrl.replace(/\/$/, '') + '/api/v1/orders/active',
      header: { 'content-type': 'application/json', Authorization: 'Bearer ' + this.globalData.token },
      success: ({ data }) => {
        // status 2 = CONSULTING（医生已接诊，进行中）
        if (!(data && data.has && data.status === 2 && data.room_id)) return;
        if (this._rejoinDismissed === data.room_id) return; // 本次已"暂不"，不再打扰
        wx.showModal({
          title: '视频问诊进行中',
          content: '您有一个进行中的视频问诊，是否进入？',
          confirmText: '进入', cancelText: '暂不',
          success: (r) => {
            if (r.confirm) {
              wx.navigateTo({
                url: `/subpackages/consult/pages/call/call?room=${data.room_id}&doctor=${data.doctor_name || ''}`,
                fail: () => {}
              });
            } else {
              this._rejoinDismissed = data.room_id; // 记住忽略，避免反复弹
            }
          }
        });
      }
    });
  },

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
  async ensureConsent() {
    if (!this.globalData.token) return false;
    if (await this.syncConsentStatus()) return true;
    const confirmed = await new Promise((resolve) => {
      wx.showModal({
        title: '互联网诊疗知情同意',
        content: '问诊前需阅读并同意《互联网诊疗知情同意书》《隐私政策》《医疗风险告知》。',
        confirmText: '同意签署',
        cancelText: '取消',
        success: (res) => resolve(!!res.confirm),
        fail: () => resolve(false)
      });
    });
    if (!confirmed) return false;
    try {
      const result = await this._consentRequest('POST', { consent_type: 'diagnosis', version: 'v1' });
      this.globalData.consentSigned = !!result.signed;
      this.globalData.consentToken = this.globalData.consentSigned ? this.globalData.token : null;
      return this.globalData.consentSigned;
    } catch (e) {
      wx.showToast({ title: '协议存证失败，请重试', icon: 'none' });
      return false;
    }
  },

  async syncConsentStatus() {
    const token = this.globalData.token;
    if (!token) {
      this.globalData.consentSigned = false;
      this.globalData.consentToken = null;
      return false;
    }
    if (this.globalData.consentSigned && this.globalData.consentToken === token) return true;
    try {
      const result = await this._consentRequest('GET');
      this.globalData.consentSigned = !!result.signed;
      this.globalData.consentToken = this.globalData.consentSigned ? token : null;
      return this.globalData.consentSigned;
    } catch (e) {
      this.globalData.consentSigned = false;
      this.globalData.consentToken = null;
      return false;
    }
  },

  _consentRequest(method, data) {
    return new Promise((resolve, reject) => {
      wx.request({
        url: this.globalData.baseUrl.replace(/\/$/, '') + '/api/v1/consents' + (method === 'GET' ? '/status' : ''),
        method,
        data,
        header: {
          'content-type': 'application/json',
          Authorization: 'Bearer ' + this.globalData.token
        },
        success: (res) => {
          if (res.statusCode >= 200 && res.statusCode < 300) resolve(res.data);
          else reject(res.data);
        },
        fail: reject
      });
    });
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
