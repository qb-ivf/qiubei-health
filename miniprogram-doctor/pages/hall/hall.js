const app = getApp();

Page({
  data: {
    onDuty: false,
    doctor: { name: '张建设', title: '主任医师', dept: '呼吸内科' },
    stats: { waiting: 3, done: 14, income: '700.00' },
    rejected: [
      { id: 99, name: '陈某', reason: '配伍禁忌' }
    ],
    queue: [
      { id: 8, no: '008', name: '李四', gender: '男', age: 45, type: '视频问诊', wait: 8, chief: '咳嗽三天，伴有低烧，感冒后自服药物效果不佳，希望详细问诊。' },
      { id: 9, no: '009', name: '王五', gender: '男', age: 32, type: '图文问诊', wait: 15 },
      { id: 10, no: '010', name: '赵六', gender: '女', age: 28, type: '视频问诊', wait: 22 }
    ]
  },

  onLoad() { this.setData({ onDuty: app.globalData.onDuty }); },

  // 接诊状态开关（OFF 置灰队列 / ON 激活）
  toggleDuty(e) {
    const onDuty = e.detail.value;
    app.globalData.onDuty = onDuty;
    this.setData({ onDuty });
    // 阶段三：调后端更新 Redis 接诊状态
  },

  // 立即接诊 → 发起 INIT_CALL → 进入 D2 开方
  accept(e) {
    if (!this.data.onDuty) {
      wx.showToast({ title: '请先开启接诊', icon: 'none' });
      return;
    }
    const id = e.currentTarget.dataset.id;
    const patient = this.data.queue.find(q => q.id === id);
    wx.navigateTo({ url: `/subpackages/consult/pages/prescribe/prescribe?room=${id}&name=${patient.name}` });
  },

  // 驳回处方重开 → 进 D2 开处方 Tab
  reopen(e) {
    const id = e.currentTarget.dataset.id;
    wx.navigateTo({ url: `/subpackages/consult/pages/prescribe/prescribe?reopen=1&order=${id}&tab=prescription` });
  }
});
