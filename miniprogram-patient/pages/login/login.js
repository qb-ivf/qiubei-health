const app = getApp();
const { request } = require('../../utils/request.js');

Page({
  data: { allowDevLogin: false },

  onLoad() {
    const account = wx.getAccountInfoSync ? wx.getAccountInfoSync() : null;
    this.setData({
      allowDevLogin: !!(account && account.miniProgram && account.miniProgram.envVersion === 'develop')
    });
  },

  // 正式主体：手机号一键授权
  onGetPhone(e) {
    const ok = e.detail.errMsg && e.detail.errMsg.indexOf('ok') > -1;
    if (!ok) {
      wx.showToast({ title: '请授权手机号后登录', icon: 'none' });
      return;
    }
    this._login(e.detail.code, null);
  },

  // 仅微信开发版显示；生产后端 DEBUG=false 时仍会拒绝 dev_phone。
  devLogin() { this._login(null, '13800000000'); },

  _login(phoneCode, devPhone) {
    wx.login({
      success: ({ code }) => {
        request('/auth/login', {
          method: 'POST', auth: false,
          data: { code, phone_code: phoneCode, dev_phone: devPhone }
        }).then((res) => {
          app.globalData.token = res.token;
          wx.setStorageSync('token', res.token);
          app.connectSignaling(); // 登录后建立信令长连接
          wx.showToast({ title: '登录成功', icon: 'success' });
          setTimeout(() => wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/index/index' }) }), 600);
        }).catch((err) => {
          wx.showToast({ title: (err && err.detail) || '登录失败（检查后端地址）', icon: 'none' });
        });
      },
      fail: () => wx.showToast({ title: '微信登录失败', icon: 'none' })
    });
  }
});
