Page({
  data: {
    steps: [
      { t: '已签收', time: '', done: false },
      { t: '配送中', time: '预计今日 18:00 前送达', done: true },
      { t: '已发货', time: '06-18 09:12', done: true },
      { t: '药房配药', time: '06-18 08:30', done: true },
      { t: '已支付药费', time: '06-17 21:05', done: true }
    ],
    drugs: [
      { name: '阿莫西林胶囊', qty: 1 },
      { name: '布洛芬缓释胶囊', qty: 1 }
    ]
  }
});
