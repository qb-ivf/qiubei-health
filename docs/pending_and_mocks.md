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
| 7 | ✅ **天津监管真实网关已接入**：SM4-CBC/SM3、9 接口映射、异步队列、退避重试、死信、每日采集、正式只读预检及连续失败/签到缺失告警均已实现；测试网关 9/9 通过，正式开关仍保持关闭 | `services/tj_gateway.py`、`tj_mappers.py`、`tj_collector.py`、`compliance_service.py`、`main.py`、`scripts/tj_preflight.py` | 余生产人员/药品补录、首次真实批次与连续多日核验 | 正式环境禁止合成测试数据 |
| 8 | ✅ **生产敏感字段加密密钥已替换**：服务器已配置有效 `ENCRYPTION_KEY`，正式预检通过；开发环境仍保留从 `JWT_SECRET` 派生的回退能力 | `backend/app/core/crypto.py`、生产 `backend/.env` | 完成（2026-07-26） | 密钥不得再次更换；已有加密数据时如需轮换，必须先做数据迁移 |
| 9 | ✅ **生产 JWT 密钥已替换**：不再使用默认值且长度通过正式预检 | 生产 `backend/.env` `JWT_SECRET` | 完成（2026-07-26） | 后续轮换会令全部旧 token 失效，须安排重新登录窗口 |
| 25 | 🟡 **生产密钥仍由服务器文件注入**：`.dockerignore` 已阻止 `.env`、支付私钥和签后文件进入镜像层；宿主机仍使用 `backend/.env`、`backend/secrets/` | `backend/.dockerignore`、生产 `.env`、`secrets/apiclient_key.pem` | 等保云资源就绪后迁 KMS/Secret Manager | 当前文件已限权 600；镜像泄密入口已关闭，剩余是外部密钥托管与轮换 |
| 26 | ✅ **运营后台真实 RBAC 与账号安全已实现**：staff+bcrypt、真实角色守卫、菜单/路由过滤、财务临床隐私；登录按账号/IP 限流并返回 `Retry-After`，Redis 键不含用户名；新增/重置密码执行 12 位、3 类字符及 bcrypt 72 字节上限 | `auth.py`、`login_security.py`、`staff_service.py`、`admin.py`、`admin-web` | 完成（现有账号不强制失效） | 连续失败锁定 15 分钟，成功登录清零；后台账号管理页同步强度提示 |
| 27 | 🟡 **腾讯云短信资质、签名和 4 个模板均已生效，代码已按真实模板对齐**：注册手机号 `2695131`（验证码+5分钟）、修改手机号 `2695133`（验证码）已分流；接口强制登录，手机号/账号/IP 多层限频，Redis 键脱敏，供应商接受发送后才保存一次性验证码；生产配置不完整时 fail-closed | `services/sms_service.py`、`api/v1/sms.py`、患者端 `add-patient.js`、`scripts/tencent_sms_preflight.py`、`docs/tencent_sms_integration.md` | 配置生产 SecretId/SecretKey/SDKAppID，部署后完成两种用途真机收码及患者端发布 | 密码重置 `2695132`、登录验证码 `2695129` 暂不接入，因为系统当前没有对应短信业务 |
| 28 | ✅ **MySQL/Redis 端口及凭据已加固**：仅绑定 `127.0.0.1:3306/6379`；应用/root 账号已分别轮换随机强口令，动态健康检查、备份和新旧账号验证均通过；生产预检数据库项 PASS | `backend/docker-compose.yml`、`services/production_readiness.py`、`scripts/production_preflight.py`、`ops-cheatsheet` 1.3 | 完成（2026-07-26） | 备份位于服务器 `/opt/backups/mysql`，权限须持续保持 700/600 |
| 29 | ✅ **API 直连端口与后台登录已加固**：宿主机 API 改为 `127.0.0.1:8000`，公网仅经 Nginx；登录限流、强密码后端门禁和前端提示已实现，生产后端与 admin-web 已发布验证 | `backend/docker-compose.yml`、`services/login_security.py`、`api/v1/auth.py`、`staff_service.py`、`admin-web/Staff.vue` | 完成（2026-07-26） | 不影响已有账号登录；只在新增/重置密码时执行新策略 |
| 30 | 🟡 **知情同意已改为服务端强制门禁**：不再信任本地缓存或 best-effort 写入；按账号/版本幂等存证，未成功存证、就诊人不归属/未实名、医生未审核、号源不匹配或视频未确认复诊时后端拒绝下单。正式协议全文及快照仍缺法务定稿 | `consents.py`、`order_service.py`、患者端 `app.js`/`doctor-detail.js` | 医院/法务提供正式协议包后增加可阅读协议页和内容摘要存证 | 需提供各文档标题、全文、版本号、生效日期、更新/撤回规则及客服渠道 |

## 🟠 P1：功能未做实 / 简化，影响体验或多端


| #  | 现状                                                                    | 位置                                                 | 何时替换                              |
| :- | :---------------------------------------------------------------------- | :--------------------------------------------------- | :------------------------------------ |
| 10 | ✅ **TRTC 前端已接**（驱动 `live-pusher/live-player`，保留自定义 UI）；用占位桩 `utils/trtc-wx.js` | 患者`video-room`、医生 `prescribe`、两端 `utils/trtc-wx.js` | 真机前两步：①小程序「实时音视频」类目审核 ②官方 trtc-wx SDK 覆盖占位桩。详见 `docs/trtc-integration.md` |
| 11 | ✅ **TRTC UserSig 已就绪**：算法实现 + 密钥已配（SDKAppID 1600148306），服务器正式预检已确认字段齐全 | `backend/app/services/trtc.py`、`api/v1/rtc.py`、生产 `backend/.env` | 服务端完成（前端官方 SDK 与类目审核见 #10） |
| 12 | ✅ **候诊队列按医生过滤**：只返回本医生名下 WAITING 订单；接诊端点加归属校验（接他人订单→404） | `backend/app/api/v1/orders.py` `doctor_queue`/`accept` | 完成 |
| 13 | ✅ **WebSocket 已支持多实例**：本机连接保留内存，Redis Pub/Sub 跨实例投递，在线状态和诊室映射带 TTL 共享；同账号新连接安全替换旧连接 | `backend/app/ws.py` | 完成 |
| 14 | ✅ **后台轮询已增加 Redis 分布式租约**：超时取消、监管队列消费不会被多个 API 实例重复执行；每日采集另有按日完成标记和失败后可重试租约 | `backend/main.py`、`services/task_lease.py` | 完成（保留轻量 asyncio 调度） |
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
| 21 | ✅ **Alembic 迁移体系已实现并接管生产库**：全新库执行版本化迁移，既有库先幂等补齐再安全 stamp；启动期不再直接 `create_all`；生产已写入 `20260726_01` | `backend/alembic/`、`scripts/db_upgrade.py`、`docker-compose.yml` | 完成（2026-07-26） |
| 22 | ✅ **小程序图标字体已自托管并完成公网校验**：按实际使用的 65 个 Material Symbols 生成 11 KB 固定子集，保留 Apache-2.0 许可证；两端只从本院 API 域名加载；生产下载 SHA-256 与仓库固定值一致 | `backend/app/static/`、两端 `app.js` | 完成（2026-07-26） |
| 23 | ✅ **生产 CORS 已收敛**：`DEBUG=false` 时只允许 `https://admin.qb-medical.cn`，预检及 OPTIONS 响应均已验证 | `backend/main.py`、`core/config.py`、生产 `backend/.env` | 完成（2026-07-26） |

---

## 外部依赖待办 （重点关注）

> **2026-07-26 结论：** 当前不依赖新账号、真实人员或云产品的代码项已清零。以下事项不能通过
> 继续编写占位代码安全完成，必须先取得对应材料或平台能力；材料到手后再按“完成判定”逐项关闭。

| 优先级 | 外部事项 | 下一步需提供/开通 | 完成判定 |
| :--: | :-- | :-- | :-- |
| P0 | 天津监管正式首批 | 医师/药师清单、药品监管字段；决定是否取消远程会诊勾选 | `tj_preflight` 0 FAIL，药品目录成功，次日批次全 success，连续观察多日 |
| P0 | 放心签首份真实签署 | 1 名医师、1 名药师完成双录；确认医院企业 CA/处方专用章 | 三方处方和两方无药病历均签署、验签、下载、追溯成功 |
| P0 | 患者实名认证 | 选定公安二要素/合规三方供应商，提供正式接口文档、应用凭据和回调/IP 白名单要求 | 错误身份被拒、正确身份通过、生产失败关闭且无身份证明文泄漏 |
| P0 | 正式诊疗协议/隐私文本 | 医院与法务定稿《互联网医疗服务协议》《知情同意书》《隐私政策》《医疗风险告知》及版本、生效日 | 患者可逐份阅读、主动勾选；服务端保存版本和内容摘要，更新后强制重新确认 |
| P0 | 腾讯云短信 | 资质 `1298330`、签名 `706643`、模板 `2695131/2695133` 均已生效；待服务器配置 SecretId/SecretKey、短信 SDKAppID | 患者端新增/修改手机号分别真机收码，内容、送达记录、一次性校验和限流验证通过 |
| P1 | TRTC 真机视频 | 小程序“实时音视频”类目审核通过；提供官方 `trtc-wx.js` SDK 文件/确定版本 | 两端真机入房、音视频、断线重连和退出闭环通过 |
| P1 | 微信订阅消息 | 正式主体下各业务模板 ID、字段映射及用户授权触发点确认 | 挂号/接诊/审方/发货等关键节点真机收到消息，拒绝授权不影响主流程 |
| P1 | 医生提现自动打款 | 微信商家转账产品开通，API 证书/公钥与产品接口权限 | 小额转账、失败重试、幂等和财务对账通过；此前继续人工打款后确认 |
| P1 | 长期归档和密钥托管 | OSS/对象锁/KMS 或 Secret Manager 资源、权限和保留策略 | 有文件异地备份恢复、对象锁、密钥轮换演练通过 |
| P2 | 在线客服入口 | 在小程序后台绑定客服人员，确认客服电话/服务时间和投诉处理渠道 | 患者端、医生端入口真机可达且有人值守；确认前不展示“建设中”按钮 |

- [x]  正式小程序 AppID ×2：患者端 ✅ `wx44cd15c9d3e4da1a`；医生端 ✅ `wx22d31040c9fcafc6`（**审核中**，待通过后真机可用）
- [x]  微信支付商户号 + 凭据（解锁 #3）— **天津逑贝互联网医院有限公司**，商户号 `1114381265`；真实 V3 下单 + 回调验签已上线验证（2026-06-24）
- [x]  腾讯云 TRTC 开通（SDKAppID 1600148306，密钥已配）；**仍待：小程序「实时音视频」类目审核 + 官方 trtc-wx SDK 覆盖占位桩**（解锁 #10）
- [x]  天津卫健委监管接口规范、测试/正式密钥及 9 接口测试联调（#7 代码完成；余生产首批）
- [x]  放心签开放平台应用 + CA 高级证书双录接口文档（#6 前半段已实现）
- [x]  放心签 PDF 签署、个人/企业签章生成、签后下载、合同验签接口文档与正式服务权限（#6 代码已实现）
- [ ]  放心签医院企业章可用性确认、人员导入/双录、首份三方签署验收及签后文件长期归档（生产密钥配置与 token 预检已完成）
- [ ]  腾讯云短信生产密钥配置，并完成患者端新增/修改手机号真机收码验证（资质、签名、模板均已完成，#27）
- [ ]  等保三级云资源（ECS/RDS/Redis/OSS + VPC）
