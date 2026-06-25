const app = getApp();
const signaling = require('../../../../utils/signaling.js');
const { request } = require('../../../../utils/request.js');
// 占位桩；上线前用官方 trtc-wx.js 覆盖 utils/trtc-wx.js。兼容 module.exports / export default
const _trtc = require('../../../../utils/trtc-wx.js');
const TRTC = (_trtc && _trtc.default) ? _trtc.default : _trtc;

const DRUG_DB = [
  { name: '阿莫西林胶囊 (Amoxicillin)', spec: '0.25g*24粒/盒', price: '18.50' },
  { name: '布洛芬缓释胶囊 (Ibuprofen)', spec: '0.3g*22粒/盒', price: '21.00' },
  { name: '连花清瘟胶囊', spec: '0.35g*24粒/盒', price: '16.80' },
  { name: '蒙脱石散', spec: '3g*10袋/盒', price: '12.30' }
];

Page({
  data: {
    statusBar: 20,
    tab: 'record',
    kbHeight: 0,
    micOn: true, cameraOn: true, ready: false,
    configured: false,      // 后端是否已配 TRTC
    pusher: {},             // 本地推流属性（医生自己）
    playerList: [],         // 远端拉流（患者，取 [0]）
    timeText: '00:00', seconds: 0,
    drugKw: '',
    suggestions: [],
    usageOptions: ['一日三次，一次一粒', '一日两次，一次一粒', '一日三次，一次两粒', '睡前服用一次'],
    drugs: [
      { name: '阿莫西林胶囊 (Amoxicillin)', spec: '0.25g*24粒/盒', price: '18.50', qty: 1, usageIdx: 0 }
    ],
    form: { present_illness: '', diagnosis: '急性上呼吸道感染', advice: '' }
  },

  onField(e) {
    this.setData({ [`form.${e.currentTarget.dataset.f}`]: e.detail.value });
  },

  onLoad(query) {
    const info = wx.getWindowInfo ? wx.getWindowInfo() : wx.getSystemInfoSync();
    this.setData({ statusBar: info.statusBarHeight || 20 });
    if (query.tab) this.setData({ tab: query.tab });
    this.roomId = query.room || '';
    this.orderId = (query.room || '').replace('room_', '') || query.order || '';
    this.fetchRtc();
    this._timer = setInterval(() => {
      const s = this.data.seconds + 1;
      this.setData({ seconds: s, timeText: `${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}` });
    }, 1000);
  },
  onUnload() { clearInterval(this._timer); this._exitRoom(); },

  // 取 TRTC 入房凭证（UserSig）→ 初始化入房
  fetchRtc() {
    request(`/rtc/user-sig?room_id=${this.roomId}`).then((c) => {
      this.rtc = c;
      if (c && c.configured) {
        // 关键：在渲染完成回调里再初始化，确保 <live-pusher> 已渲染，createPusher 才拿得到推流器
        this.setData({ configured: true }, () => this._initTRTC(c));
      } else {
        console.log('[rtc] TRTC 未配置，使用占位画面');
      }
    }).catch(() => {});
  },

  _initTRTC(c) {
    try {
      this.trtc = new TRTC(this);
      if (this.trtc.__STUB__) console.warn('[rtc] 当前为 trtc-wx 占位桩，请安装官方 SDK 后真机验证');
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
        strRoomID: String(c.roomId),
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

  // —— live-pusher / live-player 事件委托给 SDK ——
  _pusherStateChange(e) { this.trtc && this.trtc.pusherEventHandler(e); },
  _pusherNetStatus(e) { this.trtc && this.trtc.pusherNetStatusHandler(e); },
  _pusherError(e) { this.trtc && this.trtc.pusherErrorHandler(e); },
  _playerStateChange(e) { this.trtc && this.trtc.playerEventHandler(e); },
  _playerNetStatus(e) { this.trtc && this.trtc.playerNetStatus(e); },

  switchTab(e) { this.setData({ tab: e.currentTarget.dataset.t }); },

  // 步战术4：软键盘弹起 → 给作业区加 padding-bottom，顶部视频区不动
  onFocus(e) { this.setData({ kbHeight: e.detail.height || 0 }); },
  onBlur() { this.setData({ kbHeight: 0 }); },

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
  back() { wx.navigateBack(); },
  hangup() {
    wx.showModal({
      title: '结束问诊', content: '确认挂断并结束本次视频问诊？',
      confirmText: '结束', cancelText: '继续',
      success: (r) => {
        if (!r.confirm) return;
        this._exitRoom();
        // 后端置 FINISHED（患者端不再被离线补偿拉回）+ 通知患者结束
        if (this.orderId) request(`/orders/${this.orderId}/end-consult`, { method: 'POST' }).catch(() => {});
        signaling.send(signaling.SIGNAL.CALL_FINISHED, { roomId: this.roomId });
        wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/hall/hall' }) });
      }
    });
  },

  onDrugInput(e) {
    const kw = e.detail.value;
    const suggestions = kw ? DRUG_DB.filter(d => d.name.includes(kw)) : [];
    this.setData({ drugKw: kw, suggestions });
  },
  addDrug(e) {
    const d = this.data.suggestions[+e.currentTarget.dataset.i];
    if (this.data.drugs.some(x => x.name === d.name)) return;
    this.setData({ drugs: [...this.data.drugs, { ...d, qty: 1, usageIdx: 0 }], drugKw: '', suggestions: [] });
  },
  inc(e) { const i = +e.currentTarget.dataset.i; const drugs = this.data.drugs; drugs[i].qty++; this.setData({ drugs }); },
  dec(e) { const i = +e.currentTarget.dataset.i; const drugs = this.data.drugs; if (drugs[i].qty > 1) drugs[i].qty--; this.setData({ drugs }); },
  onUsage(e) { const i = +e.currentTarget.dataset.i; const drugs = this.data.drugs; drugs[i].usageIdx = +e.detail.value; this.setData({ drugs }); },
  delDrug(e) { const drugs = this.data.drugs.filter((_, idx) => idx !== +e.currentTarget.dataset.i); this.setData({ drugs }); },

  // 数字签名并发送处方 → CA 签名 loading → 订单 AUDITING → 通知患者结束 → 退回 D1
  submit() {
    if (!this.data.drugs.length) { wx.showToast({ title: '请先开具药品', icon: 'none' }); return; }
    if (!this.data.form.diagnosis) { wx.showToast({ title: '请填写初步诊断', icon: 'none' }); return; }
    if (!this.orderId) { wx.showToast({ title: '缺少订单信息', icon: 'none' }); return; }

    const items = this.data.drugs.map((d) => ({
      name: d.name, spec: d.spec, qty: d.qty,
      usage: this.data.usageOptions[d.usageIdx],
      price_fen: Math.round(parseFloat(d.price || 0) * 100)
    }));

    wx.showLoading({ title: 'CA 数字签名中...', mask: true });
    request('/prescriptions', {
      method: 'POST',
      data: {
        order_id: +this.orderId,
        present_illness: this.data.form.present_illness,
        diagnosis: this.data.form.diagnosis,
        advice: this.data.form.advice,
        items
      }
    }).then(() => {
      wx.hideLoading();
      // 通知患者端：视频结束 → 生成处方页（CALL_FINISHED）
      this._exitRoom();
      signaling.send(signaling.SIGNAL.CALL_FINISHED, { roomId: this.roomId });
      wx.showToast({ title: '处方已发送，等待药师审核', icon: 'success', duration: 1500 });
      setTimeout(() => wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/hall/hall' }) }), 1500);
    }).catch((err) => {
      wx.hideLoading();
      wx.showToast({ title: (err && err.detail) || '提交失败', icon: 'none' });
    });
  }
});
