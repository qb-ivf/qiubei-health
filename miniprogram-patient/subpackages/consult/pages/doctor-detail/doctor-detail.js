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
    patient: { name: '王小明', idMask: '320***********1234' },
    // 复诊合规声明（互联网医院仅提供复诊；天津监管 referralFlag）
    referralAgreed: false,
    originalDiagnosis: '',
    fdImages: []           // 首诊材料本地临时图（下单成功后上传，最多4张）
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

  // —— 复诊合规声明（视频问诊必须声明已在实体医院首诊）——
  toggleReferral() { this.setData({ referralAgreed: !this.data.referralAgreed }); },
  onOrigDiag(e) { this.setData({ originalDiagnosis: e.detail.value }); },

  chooseFd() {
    const left = 4 - this.data.fdImages.length;
    if (left <= 0) { wx.showToast({ title: '最多上传4张', icon: 'none' }); return; }
    wx.chooseMedia({
      count: left, mediaType: ['image'], sizeType: ['compressed'],
      success: (r) => {
        const paths = (r.tempFiles || []).map((f) => f.tempFilePath).filter(Boolean);
        this.setData({ fdImages: this.data.fdImages.concat(paths).slice(0, 4) });
      }
    });
  },
  removeFd(e) {
    const i = +e.currentTarget.dataset.i;
    this.setData({ fdImages: this.data.fdImages.filter((_, idx) => idx !== i) });
  },
  previewFd(e) {
    wx.previewImage({ current: e.currentTarget.dataset.src, urls: this.data.fdImages });
  },

  // 首诊材料逐张上传（下单成功后调用；失败不阻断问诊流程）
  uploadFdImages(orderId) {
    const paths = this.data.fdImages;
    if (!paths.length) return Promise.resolve();
    const one = (fp) => new Promise((resolve) => {
      wx.uploadFile({
        url: app.globalData.baseUrl.replace(/\/$/, '') + `/api/v1/orders/${orderId}/first-diagnosis`,
        filePath: fp, name: 'file',
        header: { Authorization: 'Bearer ' + app.globalData.token },
        complete: resolve
      });
    });
    return paths.reduce((p, fp) => p.then(() => one(fp)), Promise.resolve());
  },

  // 步战术5：挂号支付闭环
  async handlePay() {
    if (!app.ensureLogin()) return; // 登录守卫（FRD §1.2，支付前必须登录）
    if (!this.data.agreed) { wx.showToast({ title: '请先勾选协议', icon: 'none' }); return; }
    if (!this.data.selectedSlot) { wx.showToast({ title: '请选择就诊时段', icon: 'none' }); return; }
    if (this.data.service === 'video' && !this.data.referralAgreed) {
      wx.showToast({ title: '请先确认复诊声明（互联网医院仅提供复诊）', icon: 'none' });
      return;
    }
    if (!app.ensureConsent()) return; // 知情同意（首次需先签署再支付）

    const patientId = (app.globalData.currentPatient && app.globalData.currentPatient.id) || 1;
    const consultType = this.data.service;
    const res = await payRegister({
      doctorId: +this.doctorId, slotId: this.data.selectedSlot, patientId, consultType,
      referralFlag: consultType === 'video' ? this.data.referralAgreed : null,
      originalDiagnosis: this.data.originalDiagnosis
    });
    if (res.ok) {
      app.globalData.queueing = true;
      if (consultType === 'video' && this.data.fdImages.length) {
        wx.showLoading({ title: '上传首诊材料' });
        await this.uploadFdImages(res.orderId);
        wx.hideLoading();
      }
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
