// WebSocket 信令封装（步战术3）。全局长连接，分发 6 类信令。
const app = getApp();
const { SIGNAL } = require('./constants.js');

let socket = null;
const handlers = {};

function connect() {
  if (socket) return socket;
  socket = wx.connectSocket({ url: app.globalData.wsUrl, fail: () => {} });
  socket.onMessage(({ data }) => {
    let msg;
    try { msg = JSON.parse(data); } catch (e) { return; }
    const fn = handlers[msg.type];
    if (fn) fn(msg);
    // CALL_INVITE 必须挂全局：任意页面被拉起接听页（FRD 步战术3）
    if (msg.type === SIGNAL.CALL_INVITE) {
      wx.navigateTo({ url: `/subpackages/consult/pages/call/call?room=${msg.roomId}&doctor=${msg.doctorName || ''}` });
    }
  });
  socket.onClose(() => { socket = null; });
  app.globalData.socketTask = socket;
  return socket;
}

function on(type, fn) { handlers[type] = fn; }
function off(type) { delete handlers[type]; }

function send(type, payload) {
  if (!socket) return;
  socket.send({ data: JSON.stringify({ type, ...payload }) });
}

module.exports = { connect, on, off, send, SIGNAL };
