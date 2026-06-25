const { request } = require('../../utils/request.js');

Page({
  data: {
    kw: '',
    history: [],
    hot: ['中医科', '内科', '妇产科'],
    results: []
  },

  onShow() {
    // 加载真实医生用于本地检索（新增医生自动纳入）
    request('/doctors', { auth: false }).then((list) => {
      this._all = (Array.isArray(list) ? list : []).map((d) => ({
        id: d.id, name: d.name, dept: d.dept, title: d.title
      }));
    }).catch(() => { this._all = []; });
  },

  onInput(e) { this.applyKw(e.detail.value); },
  useTag(e) { this.applyKw(e.currentTarget.dataset.k); },
  onSearch(e) { this.applyKw(e.detail.value); },
  clear() { this.setData({ kw: '', results: [] }); },

  applyKw(kw) {
    const all = this._all || [];
    const results = kw ? all.filter(d => (d.name || '').includes(kw) || (d.dept || '').includes(kw)) : [];
    this.setData({ kw, results });
  },

  goDoctor(e) {
    wx.navigateTo({ url: `/subpackages/consult/pages/doctor-detail/doctor-detail?id=${e.currentTarget.dataset.id}` });
  }
});
