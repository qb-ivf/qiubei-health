const app = getApp();
const { request } = require('../../utils/request.js');

Page({
  // 正式主体：手机号一键授权
  onGetPhone(e) {
    const ok = e.detail.errMsg && e.detail.errMsg.indexOf('ok') > -1;
    if (!ok) {
      wx.showToast({ title: '测试号无法授权手机号，请用下方开发者登录', icon: 'none' });
      return;
    }
    this._login(e.detail.code, null);
  },

  // 测试号/联调：跳过手机号授权直接登录
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
