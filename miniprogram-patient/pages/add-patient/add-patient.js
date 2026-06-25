const { request } = require('../../utils/request.js');

const RELATIONS = ['本人', '父母', '配偶', '子女', '其他'];
const GENDERS = ['男', '女'];

Page({
  data: {
    id: '', isEdit: false, nameHint: '姓名',
    name: '', idCard: '', phone: '', code: '',
    genderIdx: 0, relationIdx: 0,
    genders: GENDERS, relations: RELATIONS,
    counter: 0,         // 验证码倒计时
    submitting: false
  },

  onLoad(q) {
    if (q.id) {
      const gi = GENDERS.indexOf(q.gender); const ri = RELATIONS.indexOf(q.relation);
      this.setData({
        id: q.id, isEdit: true,
        nameHint: q.name ? `原：${q.name}（不改留空）` : '姓名',
        genderIdx: gi >= 0 ? gi : 0,
        relationIdx: ri >= 0 ? ri : 0
      });
      wx.setNavigationBarTitle({ title: '编辑就诊人' });
    }
  },
  onUnload() { clearInterval(this._timer); },

  onField(e) { this.setData({ [e.currentTarget.dataset.f]: e.detail.value }); },
  onGender(e) { this.setData({ genderIdx: +e.detail.value }); },
  onRelation(e) { this.setData({ relationIdx: +e.detail.value }); },

  // 获取验证码
  getCode() {
    const phone = (this.data.phone || '').trim();
    if (!/^1\d{10}$/.test(phone)) { wx.showToast({ title: '请输入正确手机号', icon: 'none' }); return; }
    if (this.data.counter > 0) return;
    request('/sms/send-code', { method: 'POST', data: { phone } }).then((r) => {
      this.setData({ counter: 60 });
      this._timer = setInterval(() => {
        const c = this.data.counter - 1;
        this.setData({ counter: c });
        if (c <= 0) clearInterval(this._timer);
      }, 1000);
      if (r && r.dev_code) { // 开发模式自动填入
        this.setData({ code: r.dev_code });
        wx.showToast({ title: '开发模式：验证码已自动填入', icon: 'none' });
      } else {
        wx.showToast({ title: '验证码已发送', icon: 'none' });
      }
    }).catch((e) => wx.showToast({ title: (e && e.detail) || '发送失败', icon: 'none' }));
  },

  submit() {
    const name = (this.data.name || '').trim();
    const idCard = (this.data.idCard || '').trim();
    const phone = (this.data.phone || '').trim();
    const code = (this.data.code || '').trim();
    if (!this.data.isEdit && !name) { wx.showToast({ title: '请输入姓名', icon: 'none' }); return; }
    if (!this.data.isEdit && !/^\d{17}[\dXx]$/.test(idCard)) { wx.showToast({ title: '身份证号格式不正确', icon: 'none' }); return; }
    // 添加：手机号+验证码必填；编辑：仅当填了手机号才要验证码
    if (!this.data.isEdit && !/^1\d{10}$/.test(phone)) { wx.showToast({ title: '请输入手机号', icon: 'none' }); return; }
    if (phone && !code) { wx.showToast({ title: '请输入验证码', icon: 'none' }); return; }
    if (this.data.submitting) return;
    this.setData({ submitting: true });

    const gender = GENDERS[this.data.genderIdx];
    const relation = RELATIONS[this.data.relationIdx];
    let p;
    if (this.data.isEdit) {
      const data = { gender, relation };
      if (name) data.name = name;
      if (phone) { data.phone = phone; data.code = code; }
      p = request(`/patients/${this.data.id}`, { method: 'PUT', data });
    } else {
      p = request('/patients', { method: 'POST', data: { name, id_card: idCard, gender, relation, phone, code } });
    }
    p.then(() => {
      wx.showToast({ title: this.data.isEdit ? '已保存' : '添加成功', icon: 'success' });
      setTimeout(() => wx.navigateBack(), 800);
    }).catch((e) => {
      this.setData({ submitting: false });
      wx.showToast({ title: (e && e.detail) || '提交失败', icon: 'none' });
    });
  }
});
