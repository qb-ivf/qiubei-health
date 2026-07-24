const { request } = require('../../utils/request.js');

const STATUS = {
  pending: { text: '等待完成智能双录', tone: 'pending' },
  succeeded: { text: 'CA协议及智能双录已完成', tone: 'success' },
  failed: { text: '本次核验未通过', tone: 'failed' },
  expired: { text: '核验链接已过期', tone: 'failed' }
};

Page({
  data: {
    config: { enabled: false, required: false, ready: false, errors: [] },
    enrollment: null,
    statusText: '尚未发起',
    tone: 'idle',
    loading: false,
    polling: false
  },

  onLoad() { this.load(); },
  onShow() {
    if (this.data.enrollment && this.data.enrollment.status === 'pending') {
      this.pollResult(0);
    }
  },
  onUnload() {
    if (this._timer) clearTimeout(this._timer);
  },

  async load() {
    this.setData({ loading: true });
    try {
      const config = await request('/ca/config');
      let enrollment = null;
      try { enrollment = await request('/ca/enrollments/latest'); } catch (_) {}
      this.applyState(config, enrollment);
    } catch (err) {
      wx.showToast({ title: (err && err.detail) || '加载失败', icon: 'none' });
    } finally {
      this.setData({ loading: false });
    }
  },

  applyState(config, enrollment) {
    const state = enrollment ? (STATUS[enrollment.status] || { text: enrollment.status, tone: 'idle' }) : null;
    this.setData({
      config: config || this.data.config,
      enrollment: enrollment || null,
      statusText: state ? state.text : '尚未发起',
      tone: state ? state.tone : 'idle'
    });
  },

  async start() {
    if (this.data.loading) return;
    if (!this.data.config.ready) {
      const msg = (this.data.config.errors || []).join('；') || '放心签尚未配置';
      wx.showModal({ title: '暂不可发起', content: msg, showCancel: false });
      return;
    }
    this.setData({ loading: true });
    try {
      const enrollment = await request('/ca/enrollments', { method: 'POST' });
      this.applyState(this.data.config, enrollment);
      if (enrollment.agreement_url) {
        wx.navigateTo({
          url: '/pages/ca-webview/ca-webview?src=' + encodeURIComponent(enrollment.agreement_url)
        });
      } else if (enrollment.status === 'succeeded') {
        wx.showToast({ title: '已完成核验', icon: 'success' });
      }
    } catch (err) {
      wx.showModal({
        title: '发起失败',
        content: (err && err.detail) || '请稍后重试',
        showCancel: false
      });
    } finally {
      this.setData({ loading: false });
    }
  },

  refresh() { this.pollResult(0); },

  async pollResult(attempt) {
    const enrollment = this.data.enrollment;
    if (!enrollment || enrollment.status !== 'pending' || this.data.polling) return;
    this.setData({ polling: true });
    try {
      const updated = await request(`/ca/enrollments/${enrollment.order_no}/refresh`, { method: 'POST' });
      this.applyState(this.data.config, updated);
      if (updated.status === 'succeeded') {
        wx.showToast({ title: '核验成功', icon: 'success' });
      } else if (updated.status === 'pending' && attempt < 2) {
        this._timer = setTimeout(() => this.pollResult(attempt + 1), 10000);
      }
    } catch (err) {
      if (attempt < 2) {
        this._timer = setTimeout(() => this.pollResult(attempt + 1), 10000);
      } else {
        wx.showToast({ title: (err && err.detail) || '查询失败', icon: 'none' });
      }
    } finally {
      this.setData({ polling: false });
    }
  }
});
