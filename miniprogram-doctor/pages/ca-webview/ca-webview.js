Page({
  data: { src: '' },
  onLoad(options) {
    try {
      this.setData({ src: decodeURIComponent(options.src || '') });
    } catch (_) {
      wx.showToast({ title: '核验链接无效', icon: 'none' });
    }
  }
});
