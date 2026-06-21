const app = getApp();

Page({
  data: {
    user: { name: '王小明', idMask: '310***********1234' },
    orders: [
      { t: '待接诊', icon: 'pending_actions', badge: 1 },
      { t: '问诊中', icon: 'chat_bubble' },
      { t: '已完成', icon: 'task_alt' },
      { t: '退款/申诉', icon: 'payments' }
    ],
    assets: [
      { t: '我的处方', icon: 'prescriptions', color: 'var(--primary)', bg: 'rgba(0,86,196,.1)' },
      { t: '报告单查询', icon: 'lab_research', color: 'var(--secondary)', bg: 'rgba(0,108,70,.1)' },
      { t: '挂号预约记录', icon: 'calendar_month', color: 'var(--tertiary)', bg: 'rgba(137,77,0,.1)' },
      { t: '电子病历档案', icon: 'clinical_notes', color: 'var(--primary)', bg: 'rgba(0,86,196,.1)' }
    ]
  },

  onLoad() {
    const p = app.globalData.currentPatient;
    if (p) this.setData({ user: { name: p.name, idMask: p.idMask || '310***********1234' } });
  },

  goPatients() { wx.navigateTo({ url: '/pages/patients/patients' }); },
  goPrescription(e) {
    if (e.currentTarget.dataset.t === '我的处方') {
      wx.navigateTo({ url: '/subpackages/consult/pages/prescription/prescription' });
    }
  }
});
