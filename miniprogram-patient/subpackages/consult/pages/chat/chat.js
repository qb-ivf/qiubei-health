const app = getApp();
const { request } = require('../../../../utils/request.js');
const signaling = require('../../../../utils/signaling.js');

Page({
  data: {
    orderId: '', peer: '医生', myRole: 'patient',
    messages: [], input: '', baseUrl: '', scrollTo: '',
    writable: true, status: 0, hasMedicalRecord: false, hasPrescription: false
  },

  onLoad(query) {
    this.setData({
      orderId: query.orderId || '',
      peer: query.peer || '医生',
      baseUrl: (app.globalData.baseUrl || '').replace(/\/$/, '')
    });
    this.load();
    this.loadState();
  },

  onShow() {
    signaling.connect();
    this.loadState();
    signaling.on(signaling.SIGNAL.CHAT_MESSAGE, (m) => {
      if (String(m.orderId) !== String(this.data.orderId)) return;
      if (m.msg) this.append(m.msg); else this.load();
    });
    signaling.on(signaling.SIGNAL.CALL_FINISHED, (m) => this.onFinished(m));
  },
  onHide() {
    signaling.off(signaling.SIGNAL.CHAT_MESSAGE);
    signaling.off(signaling.SIGNAL.CALL_FINISHED);
  },
  onUnload() {
    signaling.off(signaling.SIGNAL.CHAT_MESSAGE);
    signaling.off(signaling.SIGNAL.CALL_FINISHED);
  },

  load() {
    request(`/orders/${this.data.orderId}/messages`).then((l) => {
      this.setData({ messages: (Array.isArray(l) ? l : []).map((m) => this._fmt(m)) }, () => this._toBottom());
    }).catch(() => {});
  },

  loadState() {
    if (!this.data.orderId) return;
    request(`/orders/${this.data.orderId}/chat-state`).then((state) => {
      this.setData({
        writable: !!state.writable,
        status: Number(state.status || 0),
        hasMedicalRecord: !!state.has_medical_record,
        hasPrescription: !!state.has_prescription
      });
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
    if (!this.data.writable) {
      wx.showToast({ title: '问诊已结束，聊天记录只读', icon: 'none' });
      return;
    }
    const c = (this.data.input || '').trim();
    if (!c) return;
    this.setData({ input: '' });
    request(`/orders/${this.data.orderId}/messages`, { method: 'POST', data: { content: c } })
      .then((m) => this.append(m))
      .catch((e) => wx.showToast({ title: (e && e.detail) || '发送失败', icon: 'none' }));
  },

  sendImage() {
    if (!this.data.writable) {
      wx.showToast({ title: '问诊已结束，聊天记录只读', icon: 'none' });
      return;
    }
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
            try {
              const body = JSON.parse(res.data);
              if (res.statusCode >= 200 && res.statusCode < 300) {
                this.append(body);
              } else {
                this.loadState();
                wx.showToast({ title: body.detail || '上传失败', icon: 'none' });
              }
            } catch (e) {
              wx.showToast({ title: '上传失败', icon: 'none' });
            }
          },
          fail: () => { wx.hideLoading(); wx.showToast({ title: '上传失败', icon: 'none' }); }
        });
      }
    });
  },

  previewImage(e) { wx.previewImage({ urls: [e.currentTarget.dataset.src] }); },

  onFinished(message) {
    if (String(message && message.orderId) !== String(this.data.orderId)) return;
    if (message.result === 'medical_record') {
      wx.showToast({ title: '问诊已完成，本次未开药', icon: 'none', duration: 1000 });
      setTimeout(() => wx.redirectTo({
        url: `/subpackages/consult/pages/medical-record/medical-record?orderId=${this.data.orderId}`
      }), 1000);
      return;
    }
    if (message.result === 'prescription') {
      wx.showToast({ title: '问诊已结束，处方审核中', icon: 'none', duration: 1000 });
      setTimeout(() => wx.redirectTo({
        url: `/subpackages/consult/pages/prescription/prescription?orderId=${this.data.orderId}`
      }), 1000);
      return;
    }
    this.loadState();
  },

  openResult() {
    if (this.data.hasPrescription) {
      wx.navigateTo({
        url: `/subpackages/consult/pages/prescription/prescription?orderId=${this.data.orderId}`
      });
      return;
    }
    if (this.data.hasMedicalRecord) {
      wx.navigateTo({
        url: `/subpackages/consult/pages/medical-record/medical-record?orderId=${this.data.orderId}`
      });
      return;
    }
    wx.showToast({ title: '问诊结果正在生成，请稍后刷新', icon: 'none' });
  }
});
