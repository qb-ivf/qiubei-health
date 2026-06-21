# qiubei-health · 逑贝互联网医院

天津逑贝互联网医院双端小程序工程。患者端与医生端是**两个物理隔离的独立小程序**（独立 AppID / codebase / 审核发布），仅通过中央服务端通信。

## 目录结构

| 目录 | 说明 | AppID |
| :--- | :--- | :--- |
| `miniprogram-patient/` | 患者端小程序「逑贝健康」 | `wx562db043af9f917c`（测试号） |
| `miniprogram-doctor/` | 医生端小程序「逑贝医生端」 | 暂用同一测试号占位，**待申请第二个测试号后替换** |
| `docs/` | FRD、开发指南、合规与架构方案 | — |

> ⚠️ 医生端 `project.config.json` 的 `appid` 目前是占位（与患者端相同），仅用于本地骨架预览；申请到第二个测试号后务必替换，否则两端无法分别提审。

## 本地开发（阶段一）

1. 用 **微信开发者工具** 分别「导入项目」`miniprogram-patient/` 与 `miniprogram-doctor/` 两个目录（各对应一个项目）。
2. 用 **VS Code** 打开仓库根目录，按提示安装推荐插件（见 `.vscode/extensions.json`），其中 **Easy Less** 负责把 `.less` 自动编译为 `.wxss`。
3. 修改任意 `.less` 保存后会在同级生成 `.wxss`；模拟器即可看到对应样式。

## 工程结构（阶段二）

```
miniprogram-patient/
├─ app.js / app.json / app.wxss      # 入口：登录守卫、状态机、分包+tabBar
├─ styles/theme.wxss                 # 共享设计系统（M3 令牌 + 工具类，对照 html/DESIGN.md）
├─ utils/                            # constants(状态机/信令) · signaling(WS) · pay(微信支付)
├─ pages/                            # 主包：index 首页 / register 预约 / message / profile / login / search / patients
└─ subpackages/consult/pages/        # 分包A：doctor-detail / call / video-room / prescription / order
miniprogram-doctor/
├─ styles/theme.wxss · utils/
├─ pages/ hall(D1) / workbench(D3) / login
└─ subpackages/consult/pages/prescribe   # D2 视频开方一体化（防软键盘遮挡）
```

## 设计系统与图标

- 颜色/字号/圆角令牌取自 `html/DESIGN.md`（Clinical Trust System，主色 `#0056c4`），统一在 `styles/theme.wxss` 中以 CSS 变量 + 工具类提供，页面 WXML 直接复用。
- 图标使用 **Material Symbols**，在 `app.js` 用 `wx.loadFontFace` 全局加载。**dev 需勾选「不校验合法域名」或将 `cdn.jsdelivr.net` 加入 downloadFile 合法域名**，否则图标可能不显示。
- 样式现以 `.wxss` 为源直接管理（已不再用 Less）。

## 待联调（阶段三）

- `utils/pay.js`、`utils/signaling.js`、各页 `app.globalData.baseUrl/wsUrl` 处的后端接口目前为 mock，联调时替换为真实 FastAPI 地址。
- `live-player`/`live-pusher` 需填入后端返回的 RTC 拉流/推流地址，并确认小程序已开通实时音视频类目。

详见 [docs/mini_program_dev_guide.md](docs/mini_program_dev_guide.md)。
