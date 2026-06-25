# TRTC 视频问诊接入说明

后端 UserSig 已就绪（`/rtc/user-sig`），前端已接好（驱动 `<live-pusher>`/`<live-player>`，保留自定义 UI）。
当前用**占位桩** `utils/trtc-wx.js`，所以能编译、能跑占位画面，但**不会真正入房**。

涉及文件：
- 患者端：`subpackages/consult/pages/video-room/`（video-room.js / .wxml）+ `utils/trtc-wx.js`
- 医生端：`subpackages/consult/pages/prescribe/`（prescribe.js / .wxml）+ `utils/trtc-wx.js`

## 真机上线三步

### 1) 小程序类目审核（硬前置）
mp.weixin.qq.com →（两个小程序都要）申请「实时播放音视频流(live-player)」「实时录制音视频流(live-pusher)」组件权限。互联网医院资质提交审核，几个工作日。**不通过组件被禁用，下面做了也没用。**

### 2) 后端配置（已完成）
服务器 `backend/.env` 配 `TRTC_SDKAPPID` / `TRTC_SECRETKEY` 并重启，使 `/rtc/user-sig` 返回 `configured=true`。

### 3) 安装官方 TRTC SDK（覆盖占位桩）

**最简方式——直接用官方 trtc-wx.js 文件覆盖两端占位桩（不用 npm 构建）：**

1. 下载官方 SDK 压缩包：**https://web.sdk.qcloud.com/trtc/miniapp/zip/trtc-wx.zip**
   （或 GitHub `LiteAVSDK/TRTC_WXMini` / npm 包 `trtc-wx`）
2. 解压，找到里面的 **`trtc-wx.js`**（在 demo 的 `utils/` 或根目录，一个几千行的单文件）。
3. 用它**覆盖**这两个文件（文件名/路径保持不变，页面代码已 `require('utils/trtc-wx.js')`）：
   - `miniprogram-patient/utils/trtc-wx.js`
   - `miniprogram-doctor/utils/trtc-wx.js`
4. 两端在微信开发者工具**重新上传体验版**。

> 页面 require 已兼容 `module.exports` 与 `export default` 两种导出，覆盖后 `new TRTC(this)` 直接可用。
> 接入代码已对齐官方 API：`createPusher()` 创建 → `on()` 监听 → **`setData({pusher: enterRoom(...)})`**（绑定的是 enterRoom 的返回值）→ 远端 `getPlayerList()`。
> 若覆盖后真机仍有问题，把开发者工具 Console 报错发给研发，按实际 SDK 版本微调 `.wxml` 的 `<live-pusher>`/`<live-player>` 属性/事件。

## 验证
1. 两台真机（患者/医生），分别登录、进同一订单的视频房间。
2. 患者端 `video-room`、医生端 `prescribe` 应能看到对方画面。
3. 麦克风/摄像头开关、切换前后摄像头、挂断（销毁流）正常。
4. 医生发处方 → 患者端收到 `CALL_FINISHED` → 跳处方页。

## 设计要点
- 本地流 = `<live-pusher>`（pusher 属性由 SDK 维护）；远端流 = `<live-player>`（取 `playerList[0]`，1对1）。
- 同一时刻只渲染一个 pusher + 一个 player（大小窗 swap 时互换位置，不会重复推流）。
- 未配置 / 未装 SDK → `configured=false`，回退占位画面，不影响其它功能。
