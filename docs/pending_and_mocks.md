# 待办 · 占位 · Mock 清单（上线前必须替换）

> 记录当前为了快速跑通 MVP 而用的 **mock / 占位 / 简化实现**，及其文件位置和"何时替换"。**上线前逐项清零**。按里程碑/优先级排列。

## 🔴 P0：涉及资金 / 合规 / 安全，上线前必须做实


| # | 现状（占位/mock）                                                 | 位置                                                                                               | 何时替换                                        | 备注                                        |
| :- | :---------------------------------------------------------------- | :------------------------------------------------------------------------------------------------- | :---------------------------------------------- | :------------------------------------------ |
| 1 | ✅ **微信登录已接真实 code2session 且生产关闭伪 openid**：两端正式 AppID/Secret 已配置；缺少凭据时仅 `DEBUG=true` 可派生开发 openid，生产直接拒绝 | `auth_service.wx_code2session`、两端 `login.js` | 完成 | 开发快捷入口只在微信开发版显示，发布版隐藏；生产后端即使被构造请求也拒绝 |
| 2 | ✅ **手机号 getPhoneNumber 已做实且生产关闭 dev_phone**：后端用 code 换 access_token（Redis 缓存）→ `getuserphonenumber`；生产授权失败直接拒绝登录，`dev_phone` 仅 DEBUG 可用 | `auth_service.wx_get_phone`/`_resolve_phone`、`auth.py`、两端 `login.js` | 完成 | 两端正式 AppID/Secret 已配置 |
| 3 | ✅✅ **真实微信支付 V3 已上线并验证，生产 mock 已封闭**（2026-06-24 实付 1 分闭环通过）：生产配置缺失时预支付拒绝、未验签回调拒绝，`pay/mock` 与 `drug-pay/mock` 返回 404；DEBUG mock 仍校验订单归属；真实 `requestPayment` 失败不再自动降级 | `pay_service.py`、`orders.py`、患者 `utils/pay.js` | 完成 | 挂号费用 `order_no`、药费用 `order_no-DRUG` 作 `out_trade_no`；部署见 `deploy/DEPLOY-ubuntu.md` |
| 4 | **实名认证**仅校验身份证格式，无三方核验                          | `backend/app/services/patient_service.py` `real_name_verify`                                       | 接公安二要素/三方                               |                                             |
| 5 | ✅ **医生资质审核闭环已实现并生产强制待审**：login 放行未审医生进入资料页；接诊/开方端点要求 approved。新医生仅在 `DEBUG=true && DOCTOR_AUTO_APPROVE=true` 时可自动通过，生产即使误配 true 也强制 pending | `auth_service.login_doctor`、`api/deps.py`、`doctors.py`、`orders.py`、`prescriptions.py`、医生端资质页 | 完成 | 人员导入可按医务审核结论显式终审 |
| 6 | 🟡 **放心签 CA 双录 + 真实 PDF 签署代码已接入**：医师/药师 H5 双录、处方三方签署、无药病历医师+医院两方签署、验签、摘要复核、受保护下载及签后 PDF 加密备份/恢复演练均已实现；原 `CA_MOCK_SIGN` 和红章占位已删除。生产密钥、迁移、正式 token 预检、回调检查及零文件归档演练均已通过；**待人员导入、企业章确认、首份真实处方/病历联调及有文件/异地归档验收** | `services/fxq_ca.py`、`ca_service.py`、`fxq_document_service.py`、`fxq_archive_service.py`、`prescription_service.py`、`scripts/fxq_storage.py` | 首份真实三方处方和两方病历签署验收 + 有文件恢复 + OSS/对象锁长期归档 | 账号主体迁移完成，合同签署/签章生成等 6 项服务已开通；详见 `docs/fangxinqian_ca_integration.md` |
| 7 | ✅ **天津监管真实网关已接入**：SM4-CBC/SM3、9 接口映射、异步队列、退避重试、死信、每日采集、正式只读预检均已实现；测试网关 9/9 通过，正式开关仍保持关闭 | `services/tj_gateway.py`、`tj_mappers.py`、`tj_collector.py`、`workers/compliance.py`、`scripts/tj_preflight.py` | 余生产人员/药品补录、首次真实批次与连续多日核验 | 正式环境禁止合成测试数据 |
| 8 | ✅ **生产敏感字段加密密钥已替换**：服务器已配置有效 `ENCRYPTION_KEY`，正式预检通过；开发环境仍保留从 `JWT_SECRET` 派生的回退能力 | `backend/app/core/crypto.py`、生产 `backend/.env` | 完成（2026-07-26） | 密钥不得再次更换；已有加密数据时如需轮换，必须先做数据迁移 |
| 9 | ✅ **生产 JWT 密钥已替换**：不再使用默认值且长度通过正式预检 | 生产 `backend/.env` `JWT_SECRET` | 完成（2026-07-26） | 后续轮换会令全部旧 token 失效，须安排重新登录窗口 |
| 25 | **生产密钥明文落盘**：APIv3 密钥 / 商户私钥 / AppSecret 以明文存于服务器 `backend/.env`、`backend/secrets/` | `backend/.env`、`backend/secrets/apiclient_key.pem` | 上线前 | 改用 KMS / 密钥管理服务或部署平台的环境变量注入；私钥文件限权 600、最小化可读账号；定期轮换 |
| 26 | ✅ **运营后台真实 RBAC 与账号安全已实现**：staff+bcrypt、真实角色守卫、菜单/路由过滤、财务临床隐私；登录按账号/IP 限流并返回 `Retry-After`，Redis 键不含用户名；新增/重置密码执行 12 位、3 类字符及 bcrypt 72 字节上限 | `auth.py`、`login_security.py`、`staff_service.py`、`admin.py`、`admin-web` | 完成（现有账号不强制失效） | 连续失败锁定 15 分钟，成功登录清零；后台账号管理页同步强度提示 |
| 27 | 🟡 **短信验证码生产已 fail-closed**：腾讯云短信配置不完整时拒绝发送且绝不回传开发验证码；开发验证码仅 `DEBUG=true` 可用 | `services/sms_service.py`、`core/config.py`、`backend/.env.example` | 生产配置腾讯云短信签名/模板及密钥后真机验证 | 配置项：`TENCENT_SMS_SECRET_ID/SECRET_KEY/SDK_APP_ID/SIGN/TEMPLATE_ID` |
| 28 | ✅ **MySQL/Redis 端口及凭据已加固**：仅绑定 `127.0.0.1:3306/6379`；应用/root 账号已分别轮换随机强口令，动态健康检查、备份和新旧账号验证均通过；生产预检数据库项 PASS | `backend/docker-compose.yml`、`services/production_readiness.py`、`scripts/production_preflight.py`、`ops-cheatsheet` 1.3 | 完成（2026-07-26） | 备份位于服务器 `/opt/backups/mysql`，权限须持续保持 700/600 |
| 29 | ✅ **API 直连端口与后台登录已加固**：宿主机 API 改为 `127.0.0.1:8000`，公网仅经 Nginx；登录限流、强密码后端门禁和前端提示已实现，生产后端与 admin-web 已发布验证 | `backend/docker-compose.yml`、`services/login_security.py`、`api/v1/auth.py`、`staff_service.py`、`admin-web/Staff.vue` | 完成（2026-07-26） | 不影响已有账号登录；只在新增/重置密码时执行新策略 |

## 🟠 P1：功能未做实 / 简化，影响体验或多端


| #  | 现状                                                                    | 位置                                                 | 何时替换                              |
| :- | :---------------------------------------------------------------------- | :--------------------------------------------------- | :------------------------------------ |
| 10 | ✅ **TRTC 前端已接**（驱动 `live-pusher/live-player`，保留自定义 UI）；用占位桩 `utils/trtc-wx.js` | 患者`video-room`、医生 `prescribe`、两端 `utils/trtc-wx.js` | 真机前两步：①小程序「实时音视频」类目审核 ②官方 trtc-wx SDK 覆盖占位桩。详见 `docs/trtc-integration.md` |
| 11 | ✅ **TRTC UserSig 已就绪**：算法实现 + 密钥已配（SDKAppID 1600148306），服务器正式预检已确认字段齐全 | `backend/app/services/trtc.py`、`api/v1/rtc.py`、生产 `backend/.env` | 服务端完成（前端官方 SDK 与类目审核见 #10） |
| 12 | ✅ **候诊队列按医生过滤**：只返回本医生名下 WAITING 订单；接诊端点加归属校验（接他人订单→404） | `backend/app/api/v1/orders.py` `doctor_queue`/`accept` | 完成 |
| 13 | **WebSocket** 用单进程内存连接管理                                      | `backend/app/ws.py`                                  | 多实例部署前                          |
| 14 | **超时取消**用 asyncio 轮询（每 30s）                                   | `backend/main.py` `_expiry_sweep`                    | 可选优化                              |
| 15 | ✅ **医生自助排班/诊金已实现**（建/查/删号源 + 改诊金，医生端「排班管理/诊金设置」页）；seed 仅本地 dev 用 | `api/v1/doctors.py` `slots`/`fee`/`my-schedule`、医生端 `pages/schedule`、`workbench` | 生产 seed 不跑（DEBUG=false）；示例医生用 `ops-cheatsheet` 4.6 清理 |
| 16 | ~~EMR/开方/药师审方~~ ✅ M5 已实现；无药问诊独立保存病历并完成，不生成空处方、不进药师审方，患者可在电子病历档案查看（真实 CA 首单见 #6） | — | 完成 |
| 17 | ~~物流/退款/消息通知~~ ✅ M7 已实现（微信订阅消息下发仍占位）           | `notification_service`                               | 订阅消息下发待正式主体                |
| 18 | 🟡 PC 后台资质终审/药品字典/监管面板已接真；医生钱包按本人隔离，`admin/finance` 可处理提现。自动转账尚未接入，当前必须由财务先在外部渠道真实打款，再在系统确认，页面已明确禁止误认为自动转账 | `admin.py`、`finance_service.py`、`admin-web/src/views/Finance.vue` | 开通并联调微信商家转账产品后再自动化打款 |
| 19 | ✅ **图文咨询闭环已完成**：两端聊天页、入口路由、`consult_type`、图片/历史/实时推送、医生填写真实病历后“开药或不开药”完成、结束后只读、患者进入处方或电子病历；最终结果由后端事务提交后推送 | `api/v1/chat.py`、`orders.py`、`prescriptions.py`、`ws.py`、两端 `pages/chat`、医生端 `pages/prescribe` | 完成 |
| 24 | ✅ **医生钱包已按本人隔离**：收入只汇总本人订单分成，审核中/已打款提现只扣本人；提现按医生行锁串行校验并写入真实姓名；无药问诊完成时幂等生成挂号分成流水 | `finance_service.doctor_balance_fen`、`create_withdrawal`、`prescription_service.complete_without_prescription` | 完成 |

## 🟡 P2：工程 / 配置


| #  | 现状                                        | 位置                                     | 何时替换                |
| :- | :------------------------------------------ | :--------------------------------------- | :---------------------- |
| 20 | ✅ **医生端 AppID 已配真号** `wx22d31040c9fcafc6`；后端 `WX_DOCTOR_*` 已配 | `miniprogram-doctor/project.config.json`、`backend/.env` | 完成（小程序后台需配 request 合法域名 + app.js 指向生产） |
| 21 | **数据库建表**用启动 `create_all`（非迁移） | `backend/main.py`                        | 引入**Alembic** 迁移    |
| 22 | **图标**依赖 jsdelivr 在线字体              | 两端`app.js` `loadFontFace`              | 可改本地字体包/自托管   |
| 23 | ✅ **生产 CORS 已收敛**：`DEBUG=false` 时只允许 `https://admin.qb-medical.cn`，预检及 OPTIONS 响应均已验证 | `backend/main.py`、`core/config.py`、生产 `backend/.env` | 完成（2026-07-26） |

---

## 外部依赖待办 （重点关注）

- [x]  正式小程序 AppID ×2：患者端 ✅ `wx44cd15c9d3e4da1a`；医生端 ✅ `wx22d31040c9fcafc6`（**审核中**，待通过后真机可用）
- [x]  微信支付商户号 + 凭据（解锁 #3）— **天津逑贝互联网医院有限公司**，商户号 `1114381265`；真实 V3 下单 + 回调验签已上线验证（2026-06-24）
- [x]  腾讯云 TRTC 开通（SDKAppID 1600148306，密钥已配）；**仍待：小程序「实时音视频」类目审核 + 官方 trtc-wx SDK 覆盖占位桩**（解锁 #10）
- [x]  天津卫健委监管接口规范、测试/正式密钥及 9 接口测试联调（#7 代码完成；余生产首批）
- [x]  放心签开放平台应用 + CA 高级证书双录接口文档（#6 前半段已实现）
- [x]  放心签 PDF 签署、个人/企业签章生成、签后下载、合同验签接口文档与正式服务权限（#6 代码已实现）
- [ ]  放心签医院企业章可用性确认、人员导入/双录、首份三方签署验收及签后文件长期归档（生产密钥配置与 token 预检已完成）
- [ ]  腾讯云短信正式签名、验证码模板和 API 密钥配置，并完成患者端/医生端真机收码验证（#27）
- [ ]  等保三级云资源（ECS/RDS/Redis/OSS + VPC）
