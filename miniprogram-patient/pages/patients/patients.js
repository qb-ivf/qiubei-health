const app = getApp();
const { request } = require('../../utils/request.js');

const MOCK = [
  { id: 1, name: '王小明', relation: '本人', verified: true, idMask: '310***********1234', active: true },
  { id: 2, name: '王老太', relation: '母亲', verified: true, idMask: '310***********5678', active: false }
];

Page({
  data: { patients: MOCK },

  onShow() { this.load(); },

  load() {
    if (!app.globalData.token) return; // 未登录用 mock 占位
    request('/patients').then((list) => {
      if (!Array.isArray(list)) return;
      const patients = list.map((p) => ({
        id: p.id, name: p.name, relation: p.relation, verified: p.verified,
        idMask: p.id_card, active: p.is_default
      }));
      if (patients.length) this.setData({ patients });
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

  // 添加就诊人（实名）。简化：用 prompt 采集，正式应做完整表单。
  addPatient() {
    if (!app.globalData.token) {
      wx.navigateTo({ url: '/pages/login/login' });
      return;
    }
    wx.showModal({
      title: '添加就诊人',
      editable: true,
      placeholderText: '格式：姓名,身份证号',
      success: (res) => {
        if (!res.confirm) return;
        const [name, idCard] = (res.content || '').split(',').map((s) => s && s.trim());
        if (!name || !idCard) { wx.showToast({ title: '请输入 姓名,身份证号', icon: 'none' }); return; }
        request('/patients', { method: 'POST', data: { name, id_card: idCard, relation: '家属' } })
          .then(() => { wx.showToast({ title: '添加成功', icon: 'success' }); this.load(); })
          .catch((err) => wx.showToast({ title: (err && err.detail) || '添加失败', icon: 'none' }));
      }
    });
  }
});
