const app = getApp();

Page({
  data: {
    doctor: { name: '张大夫', title: '主任医师' },
    manage: [
      { t: '排班管理', icon: 'calendar_month', color: 'var(--primary)', bg: 'rgba(0,86,196,.1)' },
      { t: '诊金设置', icon: 'payments', color: 'var(--secondary)', bg: 'rgba(0,108,70,.1)' },
      { t: '常用语/快捷回复', icon: 'chat_bubble', color: 'var(--tertiary)', bg: 'rgba(137,77,0,.1)' },
      { t: '多点执业/资质管理', icon: 'badge', color: 'var(--on-surface-variant)', bg: 'var(--sc-highest)' }
    ]
  },

  withdraw() { wx.showToast({ title: '提现（待接入分账接口）', icon: 'none' }); },
  tapManage(e) { wx.showToast({ title: e.currentTarget.dataset.t, icon: 'none' }); },
  logout() {
    wx.showModal({
      title: '退出登录', content: '确认退出当前账号？',
      success: (r) => {
        if (r.confirm) {
          app.globalData.token = null;
          wx.removeStorageSync('token');
          wx.reLaunch({ url: '/pages/login/login' });
        }
      }
    });
  }
});
