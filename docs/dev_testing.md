# 联调测试手册（开发期）

本文汇总后端启动、小程序导入、各里程碑测试步骤与**踩过的坑**。团队照此走可少走弯路。

---

## 一、启动后端（Windows + Docker Desktop）

在 `backend/` 目录：
```powershell
docker compose up -d --build      # 起 MySQL + Redis + api（自动建表 + seed 示例医生）
# 验证：浏览器打开 http://127.0.0.1:8000/health → {"status":"ok"}
#       接口文档 http://127.0.0.1:8000/docs
docker compose logs -f api        # 看后端日志
```

**重置数据库**（清掉测试订单/用户，重新 seed）：
```powershell
docker compose down -v ; docker compose up -d     # 约 30s 重新建表+seed
```
> 改了**模型字段**（加列）必须 `down -v` 重置——`create_all` 只建新表、不会给旧表加列。

---

## 二、导入小程序（两个项目）

微信开发者工具 →「导入项目」分别导入 `miniprogram-patient` 与 `miniprogram-doctor`，AppID 用测试号。

⭐ **两个项目都必须勾**：「详情 → 本地设置 →【不校验合法域名、web-view、TLS、HTTPS 证书】」。
> 不勾 → HTTP 请求和 **WebSocket 都连不上**，表现为"网络异常"或收不到呼叫。这是最高频的坑。

- **模拟器**：后端地址用 `http://127.0.0.1:8000`（已是默认），无需改。
- **真机预览**：改两端 `app.js` 的 `baseUrl`/`wsUrl` 为电脑局域网 IP（`ipconfig` 看 IPv4）。

登录：测试号无法用真实手机号授权，统一点登录页的「**开发者快捷登录（测试号联调用）**」。

---

## 三、分里程碑测试

### M1 账号与准入
1. 患者端点「医生详情/立即支付」未登录会被拦 → 开发者快捷登录 → 拿到 token。
2. 「我的 → 切换/添加 → 添加就诊人」，输入 `张三,11010119900307051X`（姓名,身份证）→ 添加成功（脱敏返回）。输错身份证应提示"实名信息不合法"。
3. 首次支付前弹「知情同意」，点「同意签署」存证。
4. 医生端登录 → 进接诊大厅（开发期任意账号放行；生产 `DOCTOR_AUTO_APPROVE=false` 走白名单，非白名单 403）。

### M2 挂号支付
1. 「预约挂号」→ 3 个真实医生 → 选医生 → **选就诊时段（变蓝）** → 勾协议 → 立即支付。
2. 测试号走 **mock 支付**（无商户号），看到"支付成功(模拟)" → 回首页挂**黄色排队条**。
3. Network 里依次 `orders/register`(200)、`prepay`、`pay/mock`，返回 `status:1`。
4. 号源扣减：同一时段再下单会少 1；约满弹"号源已约满"。

### M3 接诊与信令（需两个模拟器同时开）
1. **先重置数据库**（让队列干净），患者端**保持窗口开着**并登录 → 挂号支付一单。
   - 患者 Console 应有 `[ws] 已连接 ✓`。
2. 医生端登录 → 接诊大厅 →【开启接诊】开关 ON → 候诊队列出现该患者 → 点「立即接诊」。
   - 医生 Network 里 `accept` 返回 `invited:true`（true=患者在线已推送）。
3. 患者端**自动弹出全屏接听页** → 点「接听」进诊室、「拒绝」返回。✅

---

## 四、踩过的坑（速查）

| 现象 | 原因 | 解法 |
| :-- | :-- | :-- |
| 请求"网络异常"/收不到呼叫 | 没勾"不校验合法域名" | 两个项目都勾上 |
| 点按钮无反应、弹框不出 | `wx.showModal` 的 `confirmText`/`cancelText` **最多 4 个汉字** | 控制在 4 字内 |
| 改了后端代码没生效 | Windows 卷挂载 inotify 失效 | 已加 `WATCHFILES_FORCE_POLLING`；必要时 `docker compose restart api` |
| 登录报表不存在 / 加了字段没生效 | `create_all` 不改旧表 | `docker compose down -v ; up` 重置 |
| 医生接诊后患者没醒、`invited:false` | 患者 socket 未连/旧 token | 确认 `[ws] 已连接 ✓`；已支持 token 变化自动重连 |
| `wx.requestPayment` 在工具里不弹窗 | 测试号无商户号 | 已改：mock 预支付直接走 `/pay/mock` |
| 图标显示成英文单词 | Material Symbols 字体没加载 | 勾"不校验合法域名"或把 `cdn.jsdelivr.net` 加白名单 |

> 开发期"每次登录是不同用户"：dev 模式 openid 由 `wx.login` 的 code 派生，code 每次不同 → 新用户。同一登录会话内（不重新登录）uid 一致，不影响联调。
