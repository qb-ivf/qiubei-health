const app = getApp();
const { request } = require('../../utils/request.js');

Page({
  data: { patients: [] },

  onShow() { this.load(); },

  load() {
    if (!app.globalData.token) { this.setData({ patients: [] }); return; }
    request('/patients').then((list) => {
      const patients = (Array.isArray(list) ? list : []).map((p) => ({
        id: p.id, name: p.name, relation: p.relation, verified: p.verified,
        gender: p.gender || '', idMask: p.id_card, active: p.is_default
      }));
      this.setData({ patients });
      // 同步默认就诊人到全局
      const def = patients.find((p) => p.active) || patients[0];
      if (def) {
        app.globalData.currentPatient = { id: def.id, name: def.name, idMask: def.idMask };
        wx.setStorageSync('currentPatient', app.globalData.currentPatient);
      }
    }).catch(() => {});
  },

  setDefault(e) {
    const id = +e.currentTarget.dataset.id;
    const patients = this.data.patients.map((p) => ({ ...p, active: p.id === id }));
    const cur = patients.find((p) => p.active);
    this.setData({ patients });
    app.globalData.currentPatient = { id: cur.id, name: cur.name, idMask: cur.idMask };
    wx.setStorageSync('currentPatient', app.globalData.currentPatient);
    if (app.globalData.token) request(`/patients/${id}/default`, { method: 'PUT' }).catch(() => {});
    wx.showToast({ title: '已切换就诊人', icon: 'none' });
  },

  del(e) {
    const id = +e.currentTarget.dataset.id;
    const p = this.data.patients.find((x) => x.id === id);
    wx.showModal({
      title: '删除就诊人', content: `确认删除「${p ? p.name : ''}」？`,
      success: (r) => {
        if (!r.confirm) return;
        request(`/patients/${id}`, { method: 'DELETE' }).then(() => {
          if (app.globalData.currentPatient && app.globalData.currentPatient.id === id) {
            app.globalData.currentPatient = null;
            wx.removeStorageSync('currentPatient');
          }
          wx.showToast({ title: '已删除', icon: 'none' });
          this.load();
        }).catch((err) => wx.showToast({ title: (err && err.detail) || '删除失败', icon: 'none' }));
      }
    });
  },

  edit(e) {
    const id = +e.currentTarget.dataset.id;
    const p = this.data.patients.find((x) => x.id === id);
    if (!p) return;
    wx.navigateTo({ url: `/pages/add-patient/add-patient?id=${p.id}&name=${p.name}&gender=${p.gender}&relation=${p.relation}` });
  },

  addPatient() {
    if (!app.globalData.token) { wx.navigateTo({ url: '/pages/login/login' }); return; }
    wx.navigateTo({ url: '/pages/add-patient/add-patient' });
  }
});
