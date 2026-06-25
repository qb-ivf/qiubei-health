const app = getApp();
const { payRegister } = require('../../../../utils/pay.js');
const { request } = require('../../../../utils/request.js');

Page({
  data: {
    service: 'video',
    agreed: false,
    doctor: { name: '', title: '', good: '', years: 0, dept: '' },
    feeYuan: '0.00',
    slots: [],
    selectedSlot: 0,
    selectedSlotText: '',
    patient: { name: '王小明', idMask: '320***********1234' }
  },

  onLoad(query) {
    this.doctorId = query.id;
    const p = app.globalData.currentPatient;
    if (p) this.setData({ patient: { name: p.name, idMask: p.idMask || '320***********1234' } });
    this.loadDoctor();
  },

  loadDoctor() {
    request(`/doctors/${this.doctorId}`, { auth: false }).then((d) => {
      this.setData({
        doctor: { name: d.name, title: d.title, good: d.good_at || '', years: d.years || 0, dept: d.dept },
        feeYuan: (d.register_fee_fen / 100).toFixed(2)
      });
      this.loadSchedule();
    }).catch(() => {});
  },

  loadSchedule() {
    request(`/doctors/${this.doctorId}/schedule`, { auth: false }).then((slots) => {
      if (!Array.isArray(slots)) return;
      const first = slots.find((s) => s.remaining > 0) || slots[0];
      this.setData({
        slots: slots.slice(0, 6),
        selectedSlot: first ? first.id : 0,
        selectedSlotText: first ? `${first.day} ${first.start_time}-${first.end_time}` : ''
      });
    }).catch(() => {});
  },

  pickSlot(e) {
    const id = +e.currentTarget.dataset.id;
    const s = this.data.slots.find((x) => x.id === id);
    if (!s || s.remaining <= 0) return;
    this.setData({ selectedSlot: id, selectedSlotText: `${s.day} ${s.start_time}-${s.end_time}` });
  },

  selectService(e) { this.setData({ service: e.currentTarget.dataset.s }); },
  togglePolicy() { this.setData({ agreed: !this.data.agreed }); },
  switchPatient() { wx.navigateTo({ url: '/pages/patients/patients' }); },

  // 步战术5：挂号支付闭环
  async handlePay() {
    if (!app.ensureLogin()) return; // 登录守卫（FRD §1.2，支付前必须登录）
    if (!this.data.agreed) { wx.showToast({ title: '请先勾选协议', icon: 'none' }); return; }
    if (!this.data.selectedSlot) { wx.showToast({ title: '请选择就诊时段', icon: 'none' }); return; }
    if (!app.ensureConsent()) return; // 知情同意（首次需先签署再支付）

    const patientId = (app.globalData.currentPatient && app.globalData.currentPatient.id) || 1;
    const consultType = this.data.service;
    const res = await payRegister({ doctorId: +this.doctorId, slotId: this.data.selectedSlot, patientId, consultType });
    if (res.ok) {
      app.globalData.queueing = true;
      if (consultType === 'text') {
        wx.showToast({ title: '预约成功，进入问诊', icon: 'success', duration: 1000 });
        setTimeout(() => wx.redirectTo({ url: `/subpackages/consult/pages/chat/chat?orderId=${res.orderId}&peer=${this.data.doctor.name || '医生'}` }), 1000);
      } else {
        wx.showToast({ title: res.mock ? '支付成功(模拟)，安排诊室中' : '预约成功', icon: 'success', duration: 1500 });
        setTimeout(() => wx.switchTab({ url: '/pages/index/index' }), 1500);
      }
    } else if (!res.cancelled) {
      wx.showToast({ title: res.detail || '支付失败', icon: 'none' });
    }
  }
});
