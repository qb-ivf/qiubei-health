// WebSocket 信令封装（医生端）。
const app = getApp();
const { SIGNAL } = require('./constants.js');

let socket = null;
const handlers = {};

function connect() {
  if (socket) return socket;
  socket = wx.connectSocket({ url: app.globalData.wsUrl, fail: () => {} });
  socket.onMessage(({ data }) => {
    let msg; try { msg = JSON.parse(data); } catch (e) { return; }
    const fn = handlers[msg.type];
    if (fn) fn(msg);
  });
  socket.onClose(() => { socket = null; });
  app.globalData.socketTask = socket;
  return socket;
}

function on(type, fn) { handlers[type] = fn; }
function off(type) { delete handlers[type]; }
function send(type, payload) { if (socket) socket.send({ data: JSON.stringify({ type, ...payload }) }); }

module.exports = { connect, on, off, send, SIGNAL };
