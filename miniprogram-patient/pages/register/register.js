Page({
  data: {
    activeDate: 0,
    dates: [
      { label: '今日', d: '15' }, { label: '明日', d: '16' }, { label: '周一', d: '17' },
      { label: '周二', d: '18' }, { label: '周三', d: '19' }, { label: '周四', d: '20' }
    ],
    doctors: [
      { id: 1, name: '张建设', dept: '呼吸内科', title: '主任医师', fee: '50.00', pro: true, tags: ['医保可用'] },
      { id: 2, name: '王美丽', dept: '呼吸内科', title: '副主任医师', fee: '40.00', pro: false, tags: ['好评率 99%'] },
      { id: 3, name: '刘名', dept: '呼吸内科', title: '主治医师', fee: '30.00', full: true, tags: ['约满'] }
    ]
  },

  selectDate(e) { this.setData({ activeDate: +e.currentTarget.dataset.i }); },
  goSearch() { wx.navigateTo({ url: '/pages/search/search' }); },
  goDoctor(e) {
    if (e.currentTarget.dataset.full) return;
    wx.navigateTo({ url: `/subpackages/consult/pages/doctor-detail/doctor-detail?id=${e.currentTarget.dataset.id}` });
  }
});
