const app = getApp();

Page({
  onGetPhone(e) {
    if (e.detail.errMsg && e.detail.errMsg.indexOf('ok') > -1) {
      // 阶段三：把 code 交后端，校验 doctors 白名单后下发 role:doctor 的 JWT
      const token = 'mock-doctor-token-' + Date.now();
      app.globalData.token = token;
      wx.setStorageSync('token', token);
      wx.reLaunch({ url: '/pages/hall/hall' });
    } else {
      wx.showToast({ title: '已取消授权', icon: 'none' });
    }
  }
});
