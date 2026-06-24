const app = getApp();
const { request } = require('../../utils/request.js');

Page({
  onGetPhone(e) {
    const ok = e.detail.errMsg && e.detail.errMsg.indexOf('ok') > -1;
    if (!ok) {
      wx.showToast({ title: '测试号无法授权手机号，请用下方开发者登录', icon: 'none' });
      return;
    }
    this._login(e.detail.code, null);
  },

  devLogin() { this._login(null, '13900000000'); },

  _login(phoneCode, devPhone) {
    wx.login({
      success: ({ code }) => {
        request('/auth/doctor/login', {
          method: 'POST', auth: false,
          data: { code, phone_code: phoneCode, dev_phone: devPhone }
        }).then((res) => {
          app.globalData.token = res.token;
          wx.setStorageSync('token', res.token);
          app.connectSignaling(); // 登录后建立信令长连接
          // 按资质审核状态路由：approved → 接诊大厅；否则 → 资质提交/审核页
          return request('/doctors/profile');
        }).then((profile) => {
          if (profile && profile.audit_status === 'approved') {
            wx.showToast({ title: '登录成功', icon: 'success' });
            setTimeout(() => wx.reLaunch({ url: '/pages/hall/hall' }), 600);
          } else {
            wx.reLaunch({ url: '/pages/qualification/qualification' });
          }
        }).catch((err) => {
          wx.showToast({ title: (err && err.detail) || '登录失败（检查后端地址）', icon: 'none' });
        });
      },
      fail: () => wx.showToast({ title: '微信登录失败', icon: 'none' })
    });
  }
});
