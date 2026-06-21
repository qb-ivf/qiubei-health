const app = getApp();
const signaling = require('../../../../utils/signaling.js');

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
    playerSrc: '', pusherSrc: '',
    timeText: '00:00', seconds: 0,
    drugKw: '',
    suggestions: [],
    usageOptions: ['一日三次，一次一粒', '一日两次，一次一粒', '一日三次，一次两粒', '睡前服用一次'],
    drugs: [
      { name: '阿莫西林胶囊 (Amoxicillin)', spec: '0.25g*24粒/盒', price: '18.50', qty: 1, usageIdx: 0 }
    ]
  },

  onLoad(query) {
    const info = wx.getWindowInfo ? wx.getWindowInfo() : wx.getSystemInfoSync();
    this.setData({ statusBar: info.statusBarHeight || 20 });
    if (query.tab) this.setData({ tab: query.tab });
    this._timer = setInterval(() => {
      const s = this.data.seconds + 1;
      this.setData({ seconds: s, timeText: `${String(Math.floor(s/60)).padStart(2,'0')}:${String(s%60).padStart(2,'0')}` });
    }, 1000);
  },
  onUnload() { clearInterval(this._timer); },

  switchTab(e) { this.setData({ tab: e.currentTarget.dataset.t }); },

  // 步战术4：软键盘弹起 → 给作业区加 padding-bottom，顶部视频区不动
  onFocus(e) { this.setData({ kbHeight: e.detail.height || 0 }); },
  onBlur() { this.setData({ kbHeight: 0 }); },

  toggleMic() { this.setData({ micOn: !this.data.micOn }); },
  toggleCamera() { this.setData({ cameraOn: !this.data.cameraOn }); },
  back() { wx.navigateBack(); },
  hangup() { wx.navigateBack(); },

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
    wx.showLoading({ title: 'CA 数字签名中...', mask: true });
    setTimeout(() => {
      wx.hideLoading();
      // 通知患者端：视频结束 → 生成处方页（CALL_FINISHED）
      signaling.send(signaling.SIGNAL.CALL_FINISHED, {});
      wx.showToast({ title: '处方已发送，正在返回大厅', icon: 'success', duration: 1500 });
      setTimeout(() => wx.navigateBack({ fail: () => wx.switchTab({ url: '/pages/hall/hall' }) }), 1500);
    }, 1200);
  }
});
