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
用腾讯云官方 `trtc-wx` SDK **覆盖**两端的 `utils/trtc-wx.js`（文件名/路径不变）：
- 来源：https://github.com/LiteAVSDK/TRTC_WXMini → `mini/components/trtc-room/trtc-wx.js`
- 或 npm 包 `trtc-wx`。
官方 SDK 同为 `module.exports = TRTC`、`new TRTC(this)` 用法，覆盖后页面代码无需改动。

> ⚠️ 覆盖后，按官方 demo 核对两端 `.wxml` 里 `<live-pusher>`/`<live-player>` 的属性与事件名
> （不同 SDK 版本 `createPusher` 返回结构、属性名可能略有差异，.wxml 顶部有注释提示）。

## 验证
1. 两台真机（患者/医生），分别登录、进同一订单的视频房间。
2. 患者端 `video-room`、医生端 `prescribe` 应能看到对方画面。
3. 麦克风/摄像头开关、切换前后摄像头、挂断（销毁流）正常。
4. 医生发处方 → 患者端收到 `CALL_FINISHED` → 跳处方页。

## 设计要点
- 本地流 = `<live-pusher>`（pusher 属性由 SDK 维护）；远端流 = `<live-player>`（取 `playerList[0]`，1对1）。
- 同一时刻只渲染一个 pusher + 一个 player（大小窗 swap 时互换位置，不会重复推流）。
- 未配置 / 未装 SDK → `configured=false`，回退占位画面，不影响其它功能。
