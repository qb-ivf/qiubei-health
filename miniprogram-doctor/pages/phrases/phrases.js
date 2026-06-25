const { request } = require('../../utils/request.js');

Page({
  data: { list: [], input: '' },

  onShow() { this.load(); },

  load() {
    request('/doctors/phrases').then((l) => this.setData({ list: Array.isArray(l) ? l : [] })).catch(() => {});
  },

  onInput(e) { this.setData({ input: e.detail.value }); },

  add() {
    const c = (this.data.input || '').trim();
    if (!c) { wx.showToast({ title: '请输入内容', icon: 'none' }); return; }
    request('/doctors/phrases', { method: 'POST', data: { content: c } })
      .then(() => { this.setData({ input: '' }); this.load(); })
      .catch((e) => wx.showToast({ title: (e && e.detail) || '添加失败', icon: 'none' }));
  },

  del(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '删除', content: '确认删除该常用语？',
      success: (r) => {
        if (!r.confirm) return;
        request(`/doctors/phrases/${id}`, { method: 'DELETE' }).then(() => this.load()).catch(() => {});
      }
    });
  }
});
