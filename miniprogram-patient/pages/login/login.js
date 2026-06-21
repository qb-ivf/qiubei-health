const app = getApp();

Page({
  onGetPhone(e) {
    if (e.detail.errMsg && e.detail.errMsg.indexOf('ok') > -1) {
      // 阶段三：把 e.detail.code/encryptedData 交后端换取 JWT
      const token = 'mock-token-' + Date.now();
      app.globalData.token = token;
      wx.setStorageSync('token', token);
      wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/index/index' }) });
    } else {
      wx.showToast({ title: '已取消授权', icon: 'none' });
    }
  }
});
