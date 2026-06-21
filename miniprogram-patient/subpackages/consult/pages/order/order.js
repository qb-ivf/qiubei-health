const { request } = require('../../../../utils/request.js');

Page({
  data: {
    steps: [],
    drugs: []
  },

  onLoad(q) {
    this.orderId = q.orderId || '';
    this.load();
  },

  load() {
    if (!this.orderId) return;
    request(`/orders/${this.orderId}/logistics`).then((r) => {
      const steps = (r.timeline || []).map((s) => ({ t: s.t, done: s.done }));
      const drugs = (r.drugs || []).map((d) => ({ name: d.name, qty: d.qty }));
      this.setData({ steps, drugs });
    }).catch(() => {});
  }
});
