Page({
  data: {
    sessions: [
      { id: 1, title: '系统通知', desc: '您的视频问诊已预约成功，请保持手机畅通', time: '10:24', unread: 3, icon: 'notifications', color: 'var(--tertiary)', bg: 'rgba(137,77,0,.1)' },
      { id: 2, title: '处方已开具', desc: '医生已为您开具电子处方，点击查看并支付药费', time: '昨天', icon: 'prescriptions', color: 'var(--primary)', bg: 'rgba(0,86,196,.1)' },
      { id: 3, title: '张建设 医生', desc: '问诊已结束，祝您早日康复', time: '昨天', icon: 'chat', color: 'var(--secondary)', bg: 'rgba(0,108,70,.1)' },
      { id: 4, title: '物流更新', desc: '您的药品已发货，预计明日送达', time: '2天前', icon: 'local_shipping', color: 'var(--primary)', bg: 'rgba(0,86,196,.1)' }
    ]
  }
});
