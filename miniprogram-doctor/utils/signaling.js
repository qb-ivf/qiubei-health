// WebSocket 信令封装（医生端）。
const { SIGNAL } = require('./constants.js');

let socket = null;
let ready = false;
let sendQueue = [];
let heartbeat = null;
let currentToken = null;
const handlers = {};

function connect() {
  const app = getApp();
  const token = app.globalData.token;
  if (!token) return null;
  if (socket && currentToken === token) return socket;
  if (socket) { try { socket.close(); } catch (e) {} socket = null; ready = false; clearInterval(heartbeat); }
  currentToken = token;

  console.log('[ws] 连接中...', app.globalData.wsUrl);
  socket = wx.connectSocket({ url: app.globalData.wsUrl + '?token=' + token });

  socket.onOpen(() => {
    ready = true;
    console.log('[ws] 已连接 ✓');
    sendQueue.forEach((m) => socket.send({ data: m }));
    sendQueue = [];
    clearInterval(heartbeat);
    heartbeat = setInterval(() => { if (ready) socket.send({ data: JSON.stringify({ type: 'PING' }) }); }, 4000);
  });

  socket.onMessage(({ data }) => {
    let msg;
    try { msg = JSON.parse(data); } catch (e) { return; }
    if (msg.type !== 'PONG') console.log('[ws] 收到信令', msg.type);
    const fn = handlers[msg.type];
    if (fn) fn(msg);
  });

  socket.onClose(() => { console.warn('[ws] 已断开'); socket = null; ready = false; clearInterval(heartbeat); });
  socket.onError((e) => { console.error('[ws] 连接错误', e); socket = null; ready = false; clearInterval(heartbeat); });

  app.globalData.socketTask = socket;
  return socket;
}

function on(type, fn) { handlers[type] = fn; }
function off(type) { delete handlers[type]; }

function send(type, payload) {
  const m = JSON.stringify({ type, ...payload });
  if (socket && ready) socket.send({ data: m });
  else { sendQueue.push(m); connect(); }
}

module.exports = { connect, on, off, send, SIGNAL };
