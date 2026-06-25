const app = getApp();
const signaling = require('../../../../utils/signaling.js');
const { request } = require('../../../../utils/request.js');
// 占位桩；上线前用官方 trtc-wx.js 覆盖 utils/trtc-wx.js。兼容 module.exports / export default
const _trtc = require('../../../../utils/trtc-wx.js');
const TRTC = (_trtc && _trtc.default) ? _trtc.default : _trtc;

Page({
  data: {
    statusBar: 20,
    roomId: '',
    isSwapped: false,
    micOn: true, cameraOn: true, speakerOn: true,
    ready: false,           // 是否已有画面（本地入房/远端到达）
    configured: false,      // 后端是否已配 TRTC（否则走占位画面）
    pusher: {},             // 本地推流属性（TRTC SDK 维护）
    playerList: [],         // 远端拉流列表（TRTC SDK 维护，1对1 取 [0]）
    seconds: 0, timeText: '00:00'
  },

  onLoad(query) {
    const info = wx.getWindowInfo ? wx.getWindowInfo() : wx.getSystemInfoSync();
    this.setData({ statusBar: info.statusBarHeight || 20, roomId: query.room || '' });

    this.fetchRtc();

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
    this._exitRoom();
  },

  // 向后端取 TRTC 入房凭证（UserSig）
  fetchRtc() {
    request(`/rtc/user-sig?room_id=${this.data.roomId}`).then((c) => {
      this.rtc = c;
      if (c && c.configured) {
        // 关键：在渲染完成回调里再初始化，确保 <live-pusher> 已渲染，createPusher 才拿得到推流器
        this.setData({ configured: true }, () => this._initTRTC(c));
      } else {
        console.log('[rtc] TRTC 未配置，使用占位画面');
      }
    }).catch(() => {});
  },

  // 初始化 TRTC：创建本地推流器 + 监听远端流 + 入房
  _initTRTC(c) {
    try {
      this.trtc = new TRTC(this);
      if (this.trtc.__STUB__) {
        console.warn('[rtc] 当前为 trtc-wx 占位桩，请安装官方 SDK 后真机验证');
      }
      const EVENT = this.trtc.EVENT;
      this.trtc.createPusher({ beautyLevel: 0, enableCamera: this.data.cameraOn, enableMic: this.data.micOn });

      const refreshPlayers = () => this.setData({ playerList: this.trtc.getPlayerList() });
      this.trtc.on(EVENT.LOCAL_JOIN, () => { console.log('[rtc] LOCAL_JOIN ✓'); this.setData({ ready: true }); });
      this.trtc.on(EVENT.REMOTE_USER_JOIN, (e) => console.log('[rtc] REMOTE_USER_JOIN', e));
      this.trtc.on(EVENT.REMOTE_VIDEO_ADD, () => { this.setData({ ready: true }); refreshPlayers(); });
      this.trtc.on(EVENT.REMOTE_VIDEO_REMOVE, refreshPlayers);
      this.trtc.on(EVENT.REMOTE_AUDIO_ADD, refreshPlayers);
      this.trtc.on(EVENT.REMOTE_AUDIO_REMOVE, refreshPlayers);
      this.trtc.on(EVENT.ERROR, (e) => {
        const info = (e && (e.data || e.message)) || e;
        console.error('[rtc] TRTC ERROR', info);
        wx.showToast({ title: 'TRTC错误:' + JSON.stringify(info).slice(0, 100), icon: 'none', duration: 6000 });
      });

      const entered = this.trtc.enterRoom({
        sdkAppID: c.sdkAppId,
        userID: String(c.userId),
        userSig: c.userSig,
        strRoomID: String(c.roomId), // 字符串房间号（room_xxx）
        enableMic: this.data.micOn,
        enableCamera: this.data.cameraOn,
      });
      if (!entered) {
        wx.showToast({ title: '入房失败：参数无效(看Console)', icon: 'none', duration: 6000 });
        return;
      }
      // 关键：强制开启自动推流，否则只采集不进房（SDK 默认 autopush=false）
      const pusher = this.trtc.setPusherAttributes({ autopush: true });
      this.setData({ pusher });
    } catch (e) {
      console.error('[rtc] TRTC 初始化异常', e);
      wx.showToast({ title: 'TRTC异常:' + (e && e.message || e), icon: 'none', duration: 6000 });
    }
  },

  _exitRoom() {
    if (this.trtc) {
      try { this.trtc.exitRoom(); this.trtc.off(); } catch (e) {}
      this.trtc = null;
    }
  },

  // —— live-pusher / live-player 事件委托给 SDK（真实 SDK 依赖这些回调驱动状态）——
  _pusherStateChange(e) { this.trtc && this.trtc.pusherEventHandler(e); },
  _pusherNetStatus(e) { this.trtc && this.trtc.pusherNetStatusHandler(e); },
  _pusherError(e) { this.trtc && this.trtc.pusherErrorHandler(e); },
  _playerStateChange(e) { this.trtc && this.trtc.playerEventHandler(e); },
  _playerNetStatus(e) { this.trtc && this.trtc.playerNetStatus(e); },

  swap() { this.setData({ isSwapped: !this.data.isSwapped }); },

  toggleMic() {
    const micOn = !this.data.micOn;
    this.setData({ micOn });
    if (this.trtc) this.setData({ pusher: this.trtc.setPusherAttributes({ enableMic: micOn }) });
  },
  toggleCamera() {
    const cameraOn = !this.data.cameraOn;
    this.setData({ cameraOn });
    if (this.trtc) this.setData({ pusher: this.trtc.setPusherAttributes({ enableCamera: cameraOn }) });
  },
  toggleSpeaker() {
    const speakerOn = !this.data.speakerOn;
    this.setData({ speakerOn });
    // 听筒/扬声器切换：通过 pusher 的 audio-volume-type（voicecall=听筒 / media=扬声器）
    if (this.trtc) this.setData({ pusher: this.trtc.setPusherAttributes({ audioVolumeType: speakerOn ? 'media' : 'voicecall' }) });
  },
  flip() {
    if (this.trtc) this.setData({ pusher: this.trtc.switchCamera() });
  },
  noop() {},

  // 收到 CALL_FINISHED：销毁流 → 跳处方页
  onFinished() {
    this._exitRoom();
    wx.showToast({ title: '通话已结束，正在生成电子处方', icon: 'none', duration: 1000 });
    const orderId = (this.data.roomId || '').replace('room_', '');
    setTimeout(() => wx.redirectTo({ url: `/subpackages/consult/pages/prescription/prescription?orderId=${orderId}` }), 1000);
  },

  // 患者主动挂断
  hangup() {
    signaling.send(signaling.SIGNAL.CALL_FINISHED, { roomId: this.data.roomId });
    this.onFinished();
  }
});
