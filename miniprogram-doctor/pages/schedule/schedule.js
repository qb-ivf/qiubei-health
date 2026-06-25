const app = getApp();
const { request } = require('../../utils/request.js');

// 预设可排时段（上午/下午）
const PRESET = [
  { start: '09:00', end: '09:30' }, { start: '09:30', end: '10:00' }, { start: '10:00', end: '10:30' },
  { start: '10:30', end: '11:00' }, { start: '14:00', end: '14:30' }, { start: '14:30', end: '15:00' },
  { start: '15:00', end: '15:30' }, { start: '15:30', end: '16:00' }
];
const WEEK = ['日', '一', '二', '三', '四', '五', '六'];

function pad(n) { return n < 10 ? '0' + n : '' + n; }

Page({
  data: {
    days: [],          // 近 7 天 [{date:'2026-06-26', label:'今天/周一', md:'06-26'}]
    activeDay: '',
    quota: 5,
    slots: []          // 当前日的时段状态 [{start,end,id?,remaining,quota,open}]
  },

  onLoad() {
    const today = new Date();
    const days = [];
    for (let i = 0; i < 7; i++) {
      const d = new Date(today.getTime() + i * 86400000);
      const date = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
      const label = i === 0 ? '今天' : (i === 1 ? '明天' : '周' + WEEK[d.getDay()]);
      days.push({ date, label, md: `${pad(d.getMonth() + 1)}-${pad(d.getDate())}` });
    }
    this.setData({ days, activeDay: days[0].date });
    this.load();
  },

  selectDay(e) { this.setData({ activeDay: e.currentTarget.dataset.d }); this.load(); },
  changeQuota(e) { this.setData({ quota: +e.detail.value }); },

  // 拉本人号源，合并到预设时段上显示开/关 + 剩余
  load() {
    request('/doctors/my-schedule').then((list) => {
      const map = {};
      (Array.isArray(list) ? list : []).forEach((s) => {
        if (s.day === this.data.activeDay) map[s.start_time] = s;
      });
      const slots = PRESET.map((p) => {
        const s = map[p.start];
        return s
          ? { start: p.start, end: p.end, id: s.id, remaining: s.remaining, quota: s.quota, open: true }
          : { start: p.start, end: p.end, open: false };
      });
      this.setData({ slots });
    }).catch(() => {});
  },

  // 点未开 → 开号；点已开 → 删号
  toggleSlot(e) {
    const i = +e.currentTarget.dataset.i;
    const slot = this.data.slots[i];
    if (slot.open) {
      if (slot.remaining < slot.quota) { wx.showToast({ title: '该时段已有预约，不可删', icon: 'none' }); return; }
      request(`/doctors/slots/${slot.id}`, { method: 'DELETE' })
        .then(() => this.load())
        .catch((err) => wx.showToast({ title: (err && err.detail) || '删除失败', icon: 'none' }));
    } else {
      request('/doctors/slots', {
        method: 'POST',
        data: { day: this.data.activeDay, quota: this.data.quota, times: [{ start: slot.start, end: slot.end }] }
      }).then(() => this.load())
        .catch((err) => wx.showToast({ title: (err && err.detail) || '开号失败', icon: 'none' }));
    }
  },

  // 一键开放该日全部预设时段
  openAll() {
    request('/doctors/slots', {
      method: 'POST',
      data: { day: this.data.activeDay, quota: this.data.quota, times: PRESET }
    }).then(() => { this.load(); wx.showToast({ title: '已开放', icon: 'success' }); })
      .catch((err) => wx.showToast({ title: (err && err.detail) || '开号失败', icon: 'none' }));
  }
});
