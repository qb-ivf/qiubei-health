// 统一请求封装：拼 baseUrl + /api/v1，注入 JWT，401 清登录态。
const app = getApp();

function request(path, { method = 'GET', data, auth = true } = {}) {
  return new Promise((resolve, reject) => {
    const header = { 'content-type': 'application/json' };
    const token = app.globalData.token;
    if (auth && token) header.Authorization = 'Bearer ' + token;

    wx.request({
      url: app.globalData.baseUrl.replace(/\/$/, '') + '/api/v1' + path,
      method,
      data,
      header,
      success(res) {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve(res.data);
        } else {
          if (res.statusCode === 401) {
            app.globalData.token = null;
            wx.removeStorageSync('token');
          }
          reject(res.data || { detail: '请求失败' });
        }
      },
      fail(err) {
        console.error('[request fail]', app.globalData.baseUrl, path, err);
        reject({ detail: '网络异常：' + (err && err.errMsg || '请检查后端是否启动/域名校验') });
      }
    });
  });
}

module.exports = { request };
