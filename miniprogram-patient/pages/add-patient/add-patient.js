const { request } = require('../../utils/request.js');

const RELATIONS = ['本人', '父母', '配偶', '子女', '其他'];
const GENDERS = ['男', '女'];

Page({
  data: {
    name: '', idCard: '',
    genderIdx: 0, relationIdx: 0,
    genders: GENDERS, relations: RELATIONS,
    submitting: false
  },

  onField(e) { this.setData({ [e.currentTarget.dataset.f]: e.detail.value }); },
  onGender(e) { this.setData({ genderIdx: +e.detail.value }); },
  onRelation(e) { this.setData({ relationIdx: +e.detail.value }); },

  submit() {
    const name = (this.data.name || '').trim();
    const idCard = (this.data.idCard || '').trim();
    if (!name) { wx.showToast({ title: '请输入姓名', icon: 'none' }); return; }
    if (!/^\d{17}[\dXx]$/.test(idCard)) { wx.showToast({ title: '身份证号格式不正确', icon: 'none' }); return; }
    if (this.data.submitting) return;
    this.setData({ submitting: true });
    request('/patients', {
      method: 'POST',
      data: { name, id_card: idCard, gender: GENDERS[this.data.genderIdx], relation: RELATIONS[this.data.relationIdx] }
    }).then(() => {
      wx.showToast({ title: '添加成功', icon: 'success' });
      setTimeout(() => wx.navigateBack(), 800);
    }).catch((e) => {
      this.setData({ submitting: false });
      wx.showToast({ title: (e && e.detail) || '添加失败', icon: 'none' });
    });
  }
});
