const app = getApp();
const { request } = require('../../utils/request.js');

const STATUS_TEXT = { pending: '审核中', approved: '已通过', rejected: '未通过' };

Page({
  data: {
    audit_status: '',
    statusText: '',
    form: { name: '', license_no: '', practice_no: '', dept: '', title: '', years: '', good_at: '' },
    submitting: false
  },

  onLoad() { this.loadProfile(); },
  onShow() { this.loadProfile(); },

  // 拉本人档案：回填已填资料 + 当前审核状态（404=尚无记录，留空表单）
  loadProfile() {
    request('/doctors/profile').then((p) => {
      if (!p) return;
      this.setData({
        audit_status: p.audit_status || '',
        statusText: STATUS_TEXT[p.audit_status] || '',
        form: {
          name: p.name || '', license_no: p.license_no || '', practice_no: p.practice_no || '',
          dept: p.dept || '', title: p.title || '', years: p.years || '', good_at: p.good_at || ''
        }
      });
    }).catch(() => {});
  },

  onField(e) { this.setData({ [`form.${e.currentTarget.dataset.f}`]: e.detail.value }); },

  enterHall() { wx.reLaunch({ url: '/pages/hall/hall' }); },

  submit() {
    const f = this.data.form;
    if (!f.name || !f.license_no || !f.practice_no) {
      wx.showToast({ title: '请填写姓名、资格证、执业证编号', icon: 'none' });
      return;
    }
    if (this.data.submitting) return;
    this.setData({ submitting: true });
    request('/doctors/qualification', {
      method: 'POST',
      data: {
        name: f.name, license_no: f.license_no, practice_no: f.practice_no,
        dept: f.dept || null, title: f.title || null,
        years: f.years ? parseInt(f.years, 10) : null, good_at: f.good_at || null
      }
    }).then((p) => {
      this.setData({ submitting: false, audit_status: p.audit_status, statusText: STATUS_TEXT[p.audit_status] || '' });
      wx.showToast({ title: '已提交，等待审核', icon: 'success' });
    }).catch((err) => {
      this.setData({ submitting: false });
      wx.showToast({ title: (err && err.detail) || '提交失败', icon: 'none' });
    });
  },

  logout() {
    app.globalData.token = null;
    wx.removeStorageSync('token');
    wx.reLaunch({ url: '/pages/login/login' });
  }
});
