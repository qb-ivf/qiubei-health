# 待办 · 占位 · Mock 清单（上线前必须替换）

> 记录当前为了快速跑通 MVP 而用的 **mock / 占位 / 简化实现**，及其文件位置和"何时替换"。**上线前逐项清零**。按里程碑/优先级排列。

## 🔴 P0：涉及资金 / 合规 / 安全，上线前必须做实


| # | 现状（占位/mock）                                                 | 位置                                                                                               | 何时替换                                        | 备注                                        |
| :- | :---------------------------------------------------------------- | :------------------------------------------------------------------------------------------------- | :---------------------------------------------- | :------------------------------------------ |
| 1 | **微信登录**走 dev mock（openid 由 code 派生，未调 code2session） | `backend/app/services/auth_service.py` `wx_code2session`                                           | 拿到正式小程序 AppID/Secret                     | 填`WX_PATIENT_*`/`WX_DOCTOR_*` 后自动走真实 |
| 2 | ✅ **手机号 getPhoneNumber 已做实**：后端用 code 换 access_token（Redis 缓存）→ `getuserphonenumber` 解密；无密钥/失败回退 dev_phone | `auth_service.wx_get_phone`/`_resolve_phone`、`auth.py`、两端 `login.js`(已发 phone_code) | 完成 | 两端小程序均已配 AppID/Secret，真机即走真实解密 |
| 3 | ✅✅ **真实微信支付 V3 已上线并验证**（2026-06-24，生产 `https://api.qb-medical.cn` 实付 1 分闭环通过） | `backend/app/services/pay_service.py`、`api/v1/orders.py` `prepay`/`drug-prepay`/`pay/callback`、患者 `utils/pay.js` | 完成 | 凭据在 `backend/.env`（私钥 `backend/secrets/apiclient_key.pem`，gitignore）。`is_enabled()` 以 `WX_PAY_NOTIFY_URL` 为开关。挂号费用 `order_no`、药费用 `order_no-DRUG` 作 out_trade_no。`/pay/mock` 等 dev 接口保留。部署见 `deploy/DEPLOY-ubuntu.md` |
| 4 | **实名认证**仅校验身份证格式，无三方核验                          | `backend/app/services/patient_service.py` `real_name_verify`                                       | 接公安二要素/三方                               |                                             |
| 5 | ✅ **医生资质审核闭环已实现**（端到端验证通过）：login 放行未审医生、`POST /doctors/qualification` 提交、医生端资质页按状态路由、接诊/开方端点 `require_approved_doctor`。**生产可置 `DOCTOR_AUTO_APPROVE=false`** 走 admin 终审 | `auth_service.login_doctor`、`api/deps.py`、`api/v1/doctors.py`、`orders.py`、`prescriptions.py`、医生端 `pages/qualification/*`、`login.js` | 生产 .env 置 false 即生效 | 开发保留 true 便于联调；正式对外前在服务器置 false |
| 6 | 处方 PDF ✅ M9 reportlab 生成；**CA 数字签名仍占位**              | `services/compliance_service.py`                                                                   | 待**CA 合同**（SM2 云端加签）                   |                                             |
| 7 | 卫健委上报 ✅ M9 异步队列+重试+死信骨架（mock 加密/接口）         | `services/compliance_service.py`、`workers/compliance.py`                                          | 待**卫健委规范**（AES/SM4+Sign）；生产换 Celery |                                             |
| 8 | **敏感字段加密**用开发回退密钥（未设 `ENCRYPTION_KEY`）           | `backend/app/core/crypto.py`                                                                       | 正式对外前                                      | 待执行 `deploy/DEPLOY-ubuntu.md` 第 9 步生成 Fernet key。⚠️ 回退密钥派生自 `JWT_SECRET`，已有真实加密数据时换密钥需先做迁移 |
| 9 | **JWT 密钥**为默认值                                              | `backend/.env` `JWT_SECRET`                                                                        | 正式对外前                                      | 同上，deploy 第 9 步换强密钥（换后旧 token 失效，需重登录）  |
| 25 | **生产密钥明文落盘**：APIv3 密钥 / 商户私钥 / AppSecret 以明文存于服务器 `backend/.env`、`backend/secrets/` | `backend/.env`、`backend/secrets/apiclient_key.pem` | 上线前 | 改用 KMS / 密钥管理服务或部署平台的环境变量注入；私钥文件限权 600、最小化可读账号；定期轮换 |
| 26 | ✅ **运营后台真实 RBAC 已实现**：staff 账号表 + bcrypt 密码校验，登录返回真实角色（端点守卫早已按 admin/pharmacist/finance 区分） | `backend/app/api/v1/auth.py`、`models/staff.py`、`services/staff_service.py`、`scripts/create_admin.py`、`admin-web` Login.vue | 完成（账号用脚本建） | 生产建账号：`docker compose ... exec api python -m scripts.create_admin <user> <pwd> [role]`。账号建好、验证可登后，Nginx Basic Auth 门禁可保留(纵深防御)或撤除。**可改进**：按角色隐藏 admin-web 菜单（现靠端点 403 兜底） |

## 🟠 P1：功能未做实 / 简化，影响体验或多端


| #  | 现状                                                                    | 位置                                                 | 何时替换                              |
| :- | :---------------------------------------------------------------------- | :--------------------------------------------------- | :------------------------------------ |
| 10 | ✅ **TRTC 前端已接**（驱动 `live-pusher/live-player`，保留自定义 UI）；用占位桩 `utils/trtc-wx.js` | 患者`video-room`、医生 `prescribe`、两端 `utils/trtc-wx.js` | 真机前两步：①小程序「实时音视频」类目审核 ②官方 trtc-wx SDK 覆盖占位桩。详见 `docs/trtc-integration.md` |
| 11 | ✅ **TRTC UserSig 已就绪**：算法实现 + 密钥已配（SDKAppID 1600148306），签发验证通过 | `backend/app/services/trtc.py`、`api/v1/rtc.py`、`backend/.env` | 完成（待服务器 .env 同样配置 TRTC_*） |
| 12 | ✅ **候诊队列按医生过滤**：只返回本医生名下 WAITING 订单；接诊端点加归属校验（接他人订单→404） | `backend/app/api/v1/orders.py` `doctor_queue`/`accept` | 完成 |
| 13 | **WebSocket** 用单进程内存连接管理                                      | `backend/app/ws.py`                                  | 多实例部署前                          |
| 14 | **超时取消**用 asyncio 轮询（每 30s）                                   | `backend/main.py` `_expiry_sweep`                    | 可选优化                              |
| 15 | ✅ **医生自助排班/诊金已实现**（建/查/删号源 + 改诊金，医生端「排班管理/诊金设置」页）；seed 仅本地 dev 用 | `api/v1/doctors.py` `slots`/`fee`/`my-schedule`、医生端 `pages/schedule`、`workbench` | 生产 seed 不跑（DEBUG=false）；示例医生用 `ops-cheatsheet` 4.6 清理 |
| 16 | ~~EMR/开方/药师审方~~ ✅ M5 已实现（CA 签章仍占位见 #6）                | —                                                   | 完成                                  |
| 17 | ~~物流/退款/消息通知~~ ✅ M7 已实现（微信订阅消息下发仍占位）           | `notification_service`                               | 订阅消息下发待正式主体                |
| 18 | PC 后台：资质终审/药品字典/财务提现 ✅ M8 接真；监管面板 ✅ M9 接真     | —                                                   | 完成                                  |
| 19 | 🔨 **图文咨询后端已实现**（自建 WS：消息收发/图片上传/历史/WS 推送）；**待前端聊天页 + 入口路由 + 订单 consult_type** | `api/v1/chat.py`、`models/message.py`、`main.py`(/uploads 静态) | 前端聊天页 + consult_type（加列需 ALTER orders） |
| 24 | **医生钱包余额**为池化演示（未按医生维度核算）                          | `finance_service.doctor_balance_fen`                 | 上线前                                |

## 🟡 P2：工程 / 配置


| #  | 现状                                        | 位置                                     | 何时替换                |
| :- | :------------------------------------------ | :--------------------------------------- | :---------------------- |
| 20 | ✅ **医生端 AppID 已配真号** `wx22d31040c9fcafc6`；后端 `WX_DOCTOR_*` 已配 | `miniprogram-doctor/project.config.json`、`backend/.env` | 完成（小程序后台需配 request 合法域名 + app.js 指向生产） |
| 21 | **数据库建表**用启动 `create_all`（非迁移） | `backend/main.py`                        | 引入**Alembic** 迁移    |
| 22 | **图标**依赖 jsdelivr 在线字体              | 两端`app.js` `loadFontFace`              | 可改本地字体包/自托管   |
| 23 | **CORS** ✅ 代码已可配（`CORS_ORIGINS`，DEBUG=false 时生效收敛）；待填 admin-web 域名 | `backend/main.py`、`core/config.py` | 部署 admin-web 时填 `CORS_ORIGINS` |

---

## 外部依赖待办（研发 C，周期长，尽早启动）

- [x]  正式小程序 AppID ×2：患者端 ✅ `wx44cd15c9d3e4da1a`；医生端 ✅ `wx22d31040c9fcafc6`（**审核中**，待通过后真机可用）
- [x]  微信支付商户号 + 凭据（解锁 #3）— **天津逑贝互联网医院有限公司**，商户号 `1114381265`；真实 V3 下单 + 回调验签已上线验证（2026-06-24）
- [x]  腾讯云 TRTC 开通（SDKAppID 1600148306，密钥已配）；**仍待：小程序「实时音视频」类目审核 + 官方 trtc-wx SDK 覆盖占位桩**（解锁 #10）
- [ ]  卫健委监管接口规范（解锁 #7）
- [ ]  CA 电子签名合同（解锁 #6）
- [ ]  等保三级云资源（ECS/RDS/Redis/OSS + VPC）
