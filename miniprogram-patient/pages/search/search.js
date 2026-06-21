const allDoctors = [
  { id: 1, name: '张建设', dept: '呼吸内科', title: '主任医师' },
  { id: 2, name: '王美丽', dept: '呼吸内科', title: '副主任医师' },
  { id: 3, name: '李晓梅', dept: '儿科', title: '副主任医师' },
  { id: 4, name: '王志强', dept: '外科', title: '专家教授' }
];

Page({
  data: {
    kw: '',
    history: ['呼吸内科', '张建设', '咳嗽'],
    hot: ['内科', '儿科', '妇科', '皮肤科', '发热门诊'],
    results: []
  },

  onInput(e) { this.applyKw(e.detail.value); },
  useTag(e) { this.applyKw(e.currentTarget.dataset.k); },
  onSearch(e) { this.applyKw(e.detail.value); },
  clear() { this.setData({ kw: '', results: [] }); },

  applyKw(kw) {
    const results = kw ? allDoctors.filter(d => d.name.includes(kw) || d.dept.includes(kw)) : [];
    this.setData({ kw, results });
  },

  goDoctor(e) {
    wx.navigateTo({ url: `/subpackages/consult/pages/doctor-detail/doctor-detail?id=${e.currentTarget.dataset.id}` });
  }
});
