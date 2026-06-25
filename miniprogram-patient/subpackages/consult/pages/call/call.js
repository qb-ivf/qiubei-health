const app = getApp();
const signaling = require('../../../../utils/signaling.js');

Page({
  data: { doctorName: '', roomId: '' },

  onLoad(query) {
    this.setData({ doctorName: query.doctor || '', roomId: query.room || '' });
  },

  // 接听 → CALL_ANSWER → redirectTo 视频诊室（不留栈）
  async onAnswer() {
    const ok = await app.ensureMediaAuth();
    if (!ok) {
      wx.showModal({ title: '需要摄像头/麦克风权限', content: '请在右上角「···」→ 设置中开启', showCancel: false });
      return;
    }
    signaling.send(signaling.SIGNAL.CALL_ANSWER, { roomId: this.data.roomId });
    wx.redirectTo({ url: `/subpackages/consult/pages/video-room/video-room?room=${this.data.roomId}` });
  },

  // 拒绝 → CALL_REJECT → 返回
  onDecline() {
    signaling.send(signaling.SIGNAL.CALL_REJECT, { roomId: this.data.roomId });
    wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/index/index' }) });
  }
});
