const app = getApp();
const { request } = require('../../../../utils/request.js');
const signaling = require('../../../../utils/signaling.js');

Page({
  data: {
    orderId: '', peer: '医生', myRole: 'patient',
    messages: [], input: '', baseUrl: '', scrollTo: ''
  },

  onLoad(query) {
    this.setData({
      orderId: query.orderId || '',
      peer: query.peer || '医生',
      baseUrl: (app.globalData.baseUrl || '').replace(/\/$/, '')
    });
    this.load();
  },

  onShow() {
    signaling.connect();
    signaling.on(signaling.SIGNAL.CHAT_MESSAGE, (m) => {
      if (String(m.orderId) !== String(this.data.orderId)) return;
      if (m.msg) this.append(m.msg); else this.load();
    });
  },
  onHide() { signaling.off(signaling.SIGNAL.CHAT_MESSAGE); },
  onUnload() { signaling.off(signaling.SIGNAL.CHAT_MESSAGE); },

  load() {
    request(`/orders/${this.data.orderId}/messages`).then((l) => {
      this.setData({ messages: (Array.isArray(l) ? l : []).map((m) => this._fmt(m)) }, () => this._toBottom());
    }).catch(() => {});
  },

  _fmt(m) {
    return {
      id: m.id, mine: m.sender_role === this.data.myRole, type: m.type,
      content: m.type === 'image' ? this.data.baseUrl + m.content : m.content
    };
  },

  append(m) {
    this.setData({ messages: this.data.messages.concat(this._fmt(m)) }, () => this._toBottom());
  },
  _toBottom() {
    const n = this.data.messages.length;
    if (n) this.setData({ scrollTo: 'm' + this.data.messages[n - 1].id });
  },

  onInput(e) { this.setData({ input: e.detail.value }); },

  send() {
    const c = (this.data.input || '').trim();
    if (!c) return;
    this.setData({ input: '' });
    request(`/orders/${this.data.orderId}/messages`, { method: 'POST', data: { content: c } })
      .then((m) => this.append(m))
      .catch((e) => wx.showToast({ title: (e && e.detail) || '发送失败', icon: 'none' }));
  },

  sendImage() {
    wx.chooseMedia({
      count: 1, mediaType: ['image'], sizeType: ['compressed'],
      success: (r) => {
        const fp = r.tempFiles && r.tempFiles[0] && r.tempFiles[0].tempFilePath;
        if (!fp) return;
        wx.showLoading({ title: '上传中' });
        wx.uploadFile({
          url: this.data.baseUrl + '/api/v1/orders/' + this.data.orderId + '/messages/image',
          filePath: fp, name: 'file',
          header: { Authorization: 'Bearer ' + app.globalData.token },
          success: (res) => {
            wx.hideLoading();
            try { this.append(JSON.parse(res.data)); } catch (e) { wx.showToast({ title: '上传失败', icon: 'none' }); }
          },
          fail: () => { wx.hideLoading(); wx.showToast({ title: '上传失败', icon: 'none' }); }
        });
      }
    });
  },

  previewImage(e) { wx.previewImage({ urls: [e.currentTarget.dataset.src] }); }
});
