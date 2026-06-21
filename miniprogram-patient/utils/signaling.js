// WebSocket 信令封装（步战术3）。患者端：全局监听 CALL_INVITE → 任意页拉起接听页。
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
  // 已用相同 token 连上则复用；token 变了（重新登录）则重连
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
    if (msg.type !== 'PONG') console.log('[ws] 收到信令', msg.type, msg);
    const fn = handlers[msg.type];
    if (fn) fn(msg);
    // 全局：任意页面被呼叫 → 拉起接听页（FRD 页面4）
    if (msg.type === SIGNAL.CALL_INVITE) {
      wx.navigateTo({
        url: `/subpackages/consult/pages/call/call?room=${msg.roomId}&doctor=${msg.doctorName || ''}`,
        fail: (e) => console.error('[ws] 拉起接听页失败', e)
      });
    }
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
