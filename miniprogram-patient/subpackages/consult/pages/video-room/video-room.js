const app = getApp();
const signaling = require('../../../../utils/signaling.js');

Page({
  data: {
    statusBar: 20,
    roomId: '',
    isSwapped: false,
    micOn: true, cameraOn: true, speakerOn: true,
    ready: false,
    playerSrc: '', pusherSrc: '',
    seconds: 0, timeText: '00:00'
  },

  onLoad(query) {
    const info = wx.getWindowInfo ? wx.getWindowInfo() : wx.getSystemInfoSync();
    this.setData({ statusBar: info.statusBarHeight || 20, roomId: query.room || '' });

    // 阶段三：向后端换取拉流/推流地址
    // this.setData({ playerSrc: '...', pusherSrc: '...' });

    // 监听挂断信令 → 跳处方页
    signaling.on(signaling.SIGNAL.CALL_FINISHED, () => this.onFinished());

    this._timer = setInterval(() => {
      const s = this.data.seconds + 1;
      const m = String(Math.floor(s / 60)).padStart(2, '0');
      const ss = String(s % 60).padStart(2, '0');
      this.setData({ seconds: s, timeText: `${m}:${ss}` });
    }, 1000);
  },

  onUnload() {
    clearInterval(this._timer);
    signaling.off(signaling.SIGNAL.CALL_FINISHED);
  },

  onState(e) { if (e.detail.code === 2004) this.setData({ ready: true }); },
  swap() { this.setData({ isSwapped: !this.data.isSwapped }); },
  toggleMic() { this.setData({ micOn: !this.data.micOn }); },
  toggleCamera() { this.setData({ cameraOn: !this.data.cameraOn }); },
  toggleSpeaker() { this.setData({ speakerOn: !this.data.speakerOn }); },
  flip() { /* live-pusher context flip */ },
  noop() {},

  // 收到 CALL_FINISHED：销毁流 → 跳处方页（页面6）
  onFinished() {
    wx.showToast({ title: '通话已结束，正在生成电子处方', icon: 'none', duration: 1000 });
    setTimeout(() => wx.redirectTo({ url: '/subpackages/consult/pages/prescription/prescription' }), 1000);
  },

  // 患者主动挂断（演示直接走结束流程）
  hangup() {
    signaling.send(signaling.SIGNAL.CALL_FINISHED, { roomId: this.data.roomId });
    this.onFinished();
  }
});
