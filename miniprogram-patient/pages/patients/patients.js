const app = getApp();

Page({
  data: {
    patients: [
      { id: 1, name: '王小明', relation: '本人', verified: true, idMask: '310***********1234', active: true },
      { id: 2, name: '王老太', relation: '母亲', verified: true, idMask: '310***********5678', active: false }
    ]
  },

  setDefault(e) {
    const id = +e.currentTarget.dataset.id;
    const patients = this.data.patients.map(p => ({ ...p, active: p.id === id }));
    const cur = patients.find(p => p.active);
    this.setData({ patients });
    app.globalData.currentPatient = { name: cur.name, idMask: cur.idMask };
    wx.setStorageSync('currentPatient', app.globalData.currentPatient);
    wx.showToast({ title: '已切换就诊人', icon: 'none' });
  },

  addPatient() {
    wx.showToast({ title: '实名认证表单（待接入）', icon: 'none' });
  }
});
