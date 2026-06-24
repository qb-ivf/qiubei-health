/**
 * ⚠️⚠️ 占位桩（STUB），不是真正的 TRTC SDK！视频不会真正入房。
 *
 * 真机视频上线前，用腾讯云官方 trtc-wx SDK【覆盖本文件】（保持文件名/路径不变）：
 *   来源：https://github.com/LiteAVSDK/TRTC_WXMini  → mini/components/trtc-room/trtc-wx.js
 *   或 npm 包 `trtc-wx`（构建后取其 trtc-wx.js）。
 * 官方 SDK 同样 `module.exports = TRTC`、同样 new TRTC(this) 用法，覆盖后页面无需改动。
 *
 * 前置条件（缺一不可，否则覆盖了也用不了）：
 *   1) 小程序通过「实时音视频」类目审核（live-pusher / live-player 组件权限）
 *   2) 后端已配 TRTC_SDKAPPID / TRTC_SECRETKEY（/rtc/user-sig 返回 configured=true）
 *
 * 覆盖后请按官方 demo 核对各页 .wxml 里 <live-pusher>/<live-player> 的属性与事件绑定
 * （不同 SDK 版本属性名可能略有差异，已在 .wxml 注释标注）。
 */
const EVENT = {
  LOCAL_JOIN: 'LOCAL_JOIN',
  LOCAL_LEAVE: 'LOCAL_LEAVE',
  REMOTE_USER_JOIN: 'REMOTE_USER_JOIN',
  REMOTE_USER_LEAVE: 'REMOTE_USER_LEAVE',
  REMOTE_VIDEO_ADD: 'REMOTE_VIDEO_ADD',
  REMOTE_VIDEO_REMOVE: 'REMOTE_VIDEO_REMOVE',
  REMOTE_AUDIO_ADD: 'REMOTE_AUDIO_ADD',
  REMOTE_AUDIO_REMOVE: 'REMOTE_AUDIO_REMOVE',
};

class TRTC {
  constructor(ctx) {
    this._ctx = ctx;
    this._cbs = {};
    this._players = [];
    this.EVENT = EVENT;
    this.__STUB__ = true; // 真实 SDK 无此标记
  }

  createPusher(opts = {}) {
    this.pusherAttributes = Object.assign({
      url: '', mode: 'RTC', autopush: false,
      enableCamera: true, enableMic: true,
      frontCamera: 'front', beautyLevel: 0,
      audioVolumeType: 'voicecall', waitingImage: '',
    }, opts);
    return this.pusherAttributes;
  }

  setPusherAttributes(attrs = {}) {
    this.pusherAttributes = Object.assign({}, this.pusherAttributes, attrs);
    return this.pusherAttributes;
  }

  switchCamera() {
    const f = this.pusherAttributes && this.pusherAttributes.frontCamera === 'front' ? 'back' : 'front';
    return this.setPusherAttributes({ frontCamera: f });
  }

  on(evt, cb) { this._cbs[evt] = cb; }
  off() { this._cbs = {}; }
  getPlayerList() { return this._players; }

  enterRoom() {
    console.warn('[trtc-wx STUB] 未安装真实 TRTC SDK，视频不会入房。请用官方 trtc-wx.js 覆盖 utils/trtc-wx.js');
  }
  exitRoom() {}

  // 事件委托占位（真实 SDK 内含完整实现）
  pusherEventHandler() {}
  pusherNetStatusHandler() {}
  pusherErrorHandler() {}
  playerEventHandler() {}
  playerNetStatus() {}
}

module.exports = TRTC;
