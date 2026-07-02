# 天津市互联网诊疗监管平台对接实施方案（M9 落地版）

> 依据：《天津市互联网医院自建平台数据监管接口规范 ver1.0》（2025-04-23 修订，下称"规范"）。
> 本文替代 [system_roadmap.md](system_roadmap.md) 中 M9 关于卫健委上报的旧假设（原文按 AES-128-CBC + MD5 动态 Sign 预估，**实际规范为 SM4-CBC 加密 + SM3 签名的国密网关**），并给出按阶段的实施计划。
>
> 现状基线：MVP（M1–M6）与 M7/M8 大部分已实现；监管上报仅有**占位框架**（`gov_reports` 表 + 模拟 sweeper + admin 监控面板），未接真实网关。

---

## 一、对照 Roadmap 的未完成工作总览

| 里程碑 | 状态 | 未完成项 |
| :-- | :-: | :-- |
| M1–M6（MVP 闭环） | ✅ 基本完成 | 微信支付已上线（生产），无阻塞项 |
| M7 履约与通知 | 🟡 80% | 物流时间轴为演示数据；订阅消息模板未接正式 |
| M8 运营后台 | 🟡 95% | 提现"商家转账到零钱"打款未接真实；其余已完成 |
| **M9 合规网关硬化** | 🔴 **30%** | **本文主题：天津监管上报（占位→真实）、CA 正式签章、15 年归档** |
| M10 提审上线 | ⬜ 0% | 医生端正式 AppID 未申请；两端提审、等保自查 |
| 并行轨道 | 🟡 | CA 合同、监管平台账号（unitId/appKey/appSecret）、医疗类目资质 |

M9 内部三件事的优先级：**① 监管上报（本文，卡上线）→ ② CA 正式签章（处方合法性）→ ③ 音视频/处方 15 年归档**。

---

## 二、规范要点速读（协议层）

1. **准入**：向监管平台申请 `unitId`、`appKey`、`appSecret`，申请所需服务权限；调用方服务器出口 IP 需加入**白名单**（错误码 40007）。测试/正式环境地址与密钥在监管平台"申请子系统 → 技术对接 → 秘钥生成及管理"处查看。
2. **传输**：`POST https://<域名>/openapi/api`，`Content-Type: application/json`。请求体 = 业务参数**数组** JSON → **SM4（CBC）** 对称加密后的密文串。
3. **请求头**（全部必填）：

   | Header | 含义 |
   | :-- | :-- |
   | `X-Service-Id` | 固定 `his.provinceDataUploadService` |
   | `X-Service-Method` | 具体方法名（见第三节矩阵） |
   | `X-Ca-Timestamp` | 毫秒时间戳（过期→40011） |
   | `X-Ca-Nonce` | UUID 随机串 |
   | `X-Ca-key` | 平台分配的 appKey |
   | `X-Content-MD5` | 内容摘要串 |
   | `X-Ca-Signature-Headers` | 参与签名的头字段列表 |
   | `X-Ca-Signature` | 签名结果 |

4. **签名**：`sign = SM3(拼接串)`。除 `X-Ca-Signature-Headers` 外的所有头 + `requestBody`（密文），按 **key 字典序**以 `k=v&k=v` 拼接后做 SM3。
5. **返回**：外层 `code`（HTTP 层：200 成功；40001 参数错、40004 密钥不匹配、40007 IP 非法、40010 签名不合法、40011 请求过期…），内层 `body.msgCode`（业务层：200 成功；-99 字段为空，msg 用 `|` 列出字段；-98 数据为空；-1 具体失败文案）。**List 型接口中途出错即整批返回错误**，需按批重报。
6. **附件上传**：`api/uploadFile`（fileName/contentBase64/size/type），返回附件 id 集合；复诊接口的 `firstDiagnosis`（首诊材料）填多个附件 id 逗号分隔。
7. **上报节奏**：
   - 正式环境：**每日夜间固定时间**推送**前一天达到终态**的诊疗数据（一个业务编号只在终态传一次）。
   - 测试环境：各接口数据量达标即可停发（平台可查对接数量）。
   - **不良事件：每日签到**，当天无事件也要以**空数组**调用一次。
   - 评价：按 businessType 跟随上传，不强制每日签到；**须先传对应业务数据，否则被拒收**。
   - 药品目录：先备案，之后**有新增及时补传**。
8. 平台仅提供 **Java SDK**；我们是 Python（FastAPI），需按规范 1.7 的步骤图自行封装（gmssl）。

---

## 三、接口适用性矩阵（我方业务 → 规范接口）

| # | 规范接口 | X-Service-Method | 适用 | 触发/我方数据源 |
| :-: | :-- | :-- | :-: | :-- |
| 1 | 2.1.1 药品目录备案 | `uploadDrugCatalogue` | ✅ 必接 | `drugs` 表；首次全量备案 + 增改即报 |
| 2 | 2.1.3 附件上传 | `uploadFile`（`api/uploadFile`） | ✅ 必接 | 复诊首诊材料图片 |
| 3 | 2.2.1 在线咨询 | `uploadConsultIndicators` | ✅ 必接 | `consult_type=text` 图文咨询订单（终态：完成/取消） |
| 4 | 2.2.2 在线复诊 | `uploadReferralIndicators` | ✅ 必接 | `consult_type=video` 视频问诊订单（互联网医院只允许复诊，视频问诊按复诊上报） |
| 5 | 2.2.10 电子病历 | `uploadElectMedicalRecord` | ✅ 必接 | `prescriptions` 表 EMR 部分，随复诊 |
| 6 | 2.2.3 在线处方 | `uploadRecipeIndicators` | ✅ 必接 | 审方通过的处方（前一天开具） |
| 7 | 2.2.4 处方核销 | `uploadRecipeVerificationIndicators` | ✅ 必接 | 药费支付成功/处方失效（前一天核销） |
| 8 | 2.4.1 评价信息 | `uploadBusinessInfoAfter` | ✅ 必接（强制，不分业务） | **新增**评价功能 |
| 9 | 2.4.2 医疗争议（不良事件） | `pushMedicalDispute` | ✅ 必接（强制 + **每日签到**） | **新增**不良事件登记 |
| 10 | 2.2.9 预约挂号 | `uploadAppointRecord` | ❓ 待确认 | 我方"挂号"实为在线复诊预约；S0 与平台对接人确认口径 |
| 11 | 2.1.2 护理耗材目录 / 2.2.5–2.2.8 互联网护理 | — | ❌ 不适用 | 未开展互联网护理 |
| 12 | 2.3.1–2.3.6 远程医疗（门诊/会诊/影像/心电/病理/转诊） | — | ❌ 不适用 | 未开展远程医疗 |

---

## 四、差距分析（现状 vs 规范）

### 4.1 协议层（全部缺失）
- 无国密库（`gmssl` 未安装）；SM4-CBC 加密、SM3 签名、字典序拼串、X-Ca-* 请求头组装均未实现。
- 无网关配置项（网关 URL、unitId、appKey、appSecret、organID、organName 均未配置）。
- `compliance_service.process_pending()` 目前是 `random.random()` 模拟成功，未发真实请求。
- `gov_reports` 表过简：无方法名、无 payload 快照、无平台返回 msgCode/msg、无按日批次概念、无幂等唯一键。

### 4.2 数据字段缺口（按表）

| 表 | 缺失字段（→ 规范字段） | 说明 |
| :-- | :-- | :-- |
| `doctors` | `id_card_enc`（→ doctorCertID）、`subject_code/subject_name`（→ 国家诊疗科目字典 3.1）、`dept_code`（→ 科室类别字典 3.2，现 `dept` 仅存中文名） | 医生身份证加密存储，脱敏展示 |
| `staff`（药师） | `id_card_enc`、`name` 已有 →（auditDoctorId/auditDoctorCertID/auditDoctor） | 处方接口审方药师三字段必填 |
| `patients` | `cert_type`（默认 1 身份证）、`birthday`/年龄（可由身份证号解出）、监护人 `guardian_name/guardian_cert_enc/guardian_mobile`（复诊患者 <6 岁必填） | |
| `orders` | `paid_at`、`accepted_at`（→ startDate）、`finished_at`（→ endDate）、`cancel_reason/refuse_type`、`wx_transaction_id`（→ tradeNo）、`referral_flag`（是否复诊）、`original_diagnosis`（患者原诊断）、`first_diagnosis_file_ids`（首诊材料监管附件 id）、`diseases_history`（病史摘要，可复用 EMR 现病史） | 目前只有 created_at/updated_at，无业务时间戳 |
| `prescriptions` | `recipe_unique_id`（对外备查唯一随机号）、`icd_code/icd_name`（ICD-10，多个 `\|` 分隔；现 diagnosis 仅自由文本）、`recipe_type`（1 西药/2 成药/3 草药）、`effective_period/start_date/end_date`、`checked_at`（审方时间）、`rational_flag`、`is_pay/verification_status`、审方药师 id | |
| `prescriptions.items` JSON | 每味药需补：`drcode`（=drugs.id）、`drmodel`、`admission`（用法途径，字典 3.13）、`frequency`（频度）、`dosage/drunit`（每次剂量/单位）、`dosageTotal/doseUnit`（总量）、`useDays`、`otcFlag` | 现仅 name/spec/qty/usage/price_fen |
| `drugs` | `drug_class`（监管药品分类代码，字典 3.10）、`countrydrcode`（国家药品编码）、`packing`（包装规格）、`manufacturer`（产地）、`use_flag` | 药品目录备案必填 |
| 新表 `evaluations` | evaluateID/bussID/businessType/deptID/doctorId/satisfaction(1-5)/scoring(0-10)/evaluation/evaluationPeople/evaluationTime | 患者端评价功能整体缺失 |
| 新表 `medical_disputes` | eventID/businessType/patientName/mobile/eventDescription/eventDate/eventReason/takeSteps/damageDegree/improvements/reportDept/reportPerson/reportDate | 不良事件登记功能整体缺失 |
| 新表 `icd10_codes` | code/name（国家临床版 2.0 ICD-10） | 开方诊断从"自由文本"改为"字典选择" |
| 机构配置 | `ORGAN_ID`（统一组织机构代码）、`TJ_UNIT_ID`、`ORGAN_NAME`、`TJ_APP_KEY/SECRET`、`TJ_GATEWAY_URL` | `.env` + `settings` |

### 4.3 业务功能缺口（不只是字段）
1. **评价**：患者端订单完成后评分入口 + 后端 CRUD（→ 接口 8）。
2. **不良事件登记**：admin-web 录入页 + 每日签到任务（→ 接口 9）。
3. **复诊合规闭环**：患者下视频单时须声明"已在实体医院确诊"（referralFlag）、填原诊断、上传首诊材料图片；医生接诊界面展示。**这是互联网医院"只能复诊"的监管红线**，目前产品流程完全没有。
4. **ICD-10 选择器**：医生端开方时诊断改为搜索选择（可多选），落 `icd_code/icd_name`。
5. **药品目录治理**：admin-web 药品字典补维护"监管分类代码/国家药品编码/包装/产地"，保存时触发目录上报。
6. **医生/药师建档补录**：admin-web 资质页补录身份证号、诊疗科目编码、科室类别编码。

---

## 五、目标架构

```
业务事件（订单终态/审方通过/药费支付/评价/不良事件/药品变更）
        │  enqueue(biz_type, biz_id)          ← 已有，保留
        ▼
gov_reports（升级：+method +payload +batch_date +msg_code +uniq(biz_type,biz_id)）
        ▲                                      │
每日 01:30 采集器（collector）                 │ 后台 worker（沿用 asyncio sweeper，
  按接口扫描前一日终态数据 → 组包入队           │ 真实发送替换 random 模拟）
                                               ▼
                              TjGatewayClient（新增 app/services/tj_gateway.py）
                              SM4-CBC 加密 → SM3 签名 → X-Ca-* 头 → httpx POST
                                               │
                                               ▼
                          天津监管平台 /openapi/api（测试 → 正式）
```

设计取舍：
- **沿用现有 asyncio 后台任务**（`main.py` 的 sweep 模式）做 worker 与每日调度，不强行引入 Celery Beat——单机生产够用、改动最小；若后续多实例部署再迁 Celery（骨架已在 `workers/compliance.py`）。
- **payload 在入队时快照**（JSON 落库），保证重报时数据与当日一致、可在后台查看审计。
- 幂等：`(biz_type, biz_id)` 唯一索引；终态才入队，重复入队直接忽略。

---

## 六、分阶段实施计划

> 建议节奏：S0 立即启动（非研发阻塞项），S1–S4 为研发主线（约 3–4 周），S5 联调转正式。每阶段有明确验收，通过再进下一阶段。

### S0 · 前置准备（并行，负责人：C 角/项目负责人，本周启动）

> 详细操作步骤已展开为独立手册：**[tianjin_supervision_s0_checklist.md](tianjin_supervision_s0_checklist.md)**（含账号收权、外包商存量上报摸底、切换窗口方案——我院 2023 年已持牌、此前由外包商代报，S0 核心是收权而非新入驻）。

任务概览（细节见手册）：

| # | 任务 | 状态 |
| :-: | :-- | :-: |
| T1 | 监管平台机构账号收权（入口 `imssp.wsjk.tj.gov.cn`），改密 | ☐ |
| T2 | 摸底外包商存量上报现状（接口对接数量/不良事件签到是否断报/bussID 形态） | ☐ |
| T3 | 测试环境密钥（unitId/appKey/appSecret）+ 9 个方法权限 + IP 白名单 | ☐ |
| T4 | 首次连通性验证：跑 `backend/scripts/tj_ping.py`（内置黄金向量自检） | ☐ |
| T5 | 10 项口径问题书面确认（复诊口径/预约挂号是否需要/达标标准/幂等等） | ☐ |
| T6 | 四份字典对照表（医生科目/科室类别/药品分类+国家药品编码/ICD-10 源） | ☐ |
| T7 | organID 核对 + 正式环境切换窗口方案（含外包商密钥重置时机与回退预案） | ☐ |
| — | ~~下载 Java SDK 并对拍加密/签名规则~~ | ✅ 已完成 |

✅ **协议已提前确认**：官方 jar 已到手并完成逆向对拍，SM4-CBC（appSecret 为 32 位 hex 密钥、固定 IV）、SM3 签名（TreeMap 字典序 + `小写头名:值` + `&` 连接）、X-Content-MD5 实为 SM3 等全部细节及**黄金测试向量**已固化在 **[tianjin_gateway_protocol.md](tianjin_gateway_protocol.md)**——S1 最大不确定项已消除。

**验收：** 见手册末尾 DoD 清单；核心是 `tj_ping.py` 对测试网关返回 `msgCode=200`。

### S1 · 国密网关客户端（研发 B，协议已确认，压缩为约 2 天）

新增 `backend/app/services/tj_gateway.py` + `backend/app/utils/sm_crypto.py`，**实现细则与对拍向量见 [tianjin_gateway_protocol.md](tianjin_gateway_protocol.md)**（`tj_ping.py` 中的 `sm3_hex_upper/sm4_encrypt_hex/build_headers` 三个函数即为参考实现，搬入正式模块即可）：

- [x] `requirements.txt` 增加 `gmssl`。
- [x] `sm_crypto.py`：SM4-CBC（key=hex 解码的 appSecret，IV 固定 `abcd0863…`，**ISO7816-4 填充**——实测非 PKCS7，输出小写 hex）；SM3（输出转大写）。
- [x] `tj_gateway.py`：
  - `build_sign_headers(...)`：按协议文档第一节组装（requestBody 不进签名串，经 X-Content-MD5 间接绑定）；
  - `tj_call(method, payload) -> TjResult`：POST 密文本体；`code=-1/40011/超时/5xx` 可重试，`-99/-98/40001/业务-1` 为数据错误（不自动重试，进失败列表待人工）；
  - `tj_upload_file(...)`：走 `api/uploadFile`，**明文不加密**（executeNoEncode 路径），X-Content-MD5=SM3(明文)。
- [x] `config.py`/`.env` 新增：`TJ_GATEWAY_URL`、`TJ_APP_KEY`、`TJ_APP_SECRET`、`TJ_UNIT_ID`、`ORGAN_ID`、`ORGAN_NAME`、`TJ_REPORT_ENABLED`（开关，默认 false 保持现状占位）。
- [x] 单元测试 `tests/test_tj_gateway.py`：黄金向量 V1–V9 全部断言，**7 passed** ✅。
- [ ] 待 S0 T3 拿到测试密钥：`tj_ping.py` 打真实网关，完成最终验收。

**验收：** ~~单测 V1–V9 全绿~~ ✅ 已达成；剩余：测试环境用真密钥调用 `uploadDrugCatalogue` 传 1 条演示药品，收到 `msgCode=200`。

### S2 · 数据模型与业务功能补齐（研发 B + A，约 1 周）

后端（`scripts/migrate.py` 补列 + 模型修改）：

- [x] `orders` 加列：paid_at/accepted_at/finished_at/cancel_reason/wx_transaction_id/**wx_drug_transaction_id**（挂号与药费流水分开存）/referral_flag/original_diagnosis/first_diagnosis_file_ids；`prescriptions` 加 icd_code/icd_name。migrate.py 已同步。
- [ ] 其余表加列：`doctors`（身份证/科目编码/科室编码）、`staff`（身份证）、`patients`（证件类型/监护人）、`prescriptions`（recipe_unique_id/recipe_type/effective_period/checked_at/rational_flag 等）、`drugs`（drug_class/countrydrcode/packing/manufacturer/use_flag）——依赖 S0 T6 字典对照表与 admin 补录页，随其一起做。
- [x] 状态机埋时间戳：支付回调写 `paid_at`+微信流水号（真实回调透传 `transaction_id`）；接诊 `1→2` 写 `accepted_at`；FINISHED/REFUNDED/CANCELLED 写 `finished_at`；超时取消/退款写 `cancel_reason`。集中在 `order_service._stamp()`，幂等只写首次。
- [x] 新表 `icd10_codes`（west 35862 条 + tcm 1890 条）+ 导入脚本 `scripts/import_icd10.py`（幂等，`--force` 重导，直接读归档 xlsx）。
- [ ] 新表：`evaluations`、`medical_disputes` + 评价 API、不良事件 CRUD（admin）。
- [x] 开方接口：`PrescriptionCreate` 接受 `icd_code/icd_name`（多个 `|` 分隔）落库；搜索接口 `GET /api/v1/icd10?q=`（编码前缀/名称模糊，west/tcm/all）。
- [ ] 开方 items 结构扩展校验（用法/频度/剂量/天数必填）——与医生端表单改版一起做。

前端：

- [ ] **患者端小程序**：视频挂号流程加"复诊声明"页（referralFlag 勾选 + 原诊断填写 + 首诊材料拍照上传）；订单完成后评价页（星级 1–5 + 0–10 分 + 文本）。
- [ ] **医生端小程序**：开方页诊断改 ICD-10 搜索选择；处方明细补用法/频度/剂量/天数表单；接诊页展示患者首诊材料。
- [ ] **admin-web**：医生资质页补录身份证/科目/科室编码；药品字典页补监管字段；新增"不良事件登记"页（menu：合规管理）。

**验收：** 新开一单完整走通后，该订单/处方/药品数据能满足第三节各接口的**必输（Y）字段**无一为空（写一个 `scripts/check_report_ready.py` 自检脚本逐字段核验）。

### S3 · 上报映射与调度（研发 B，约 1 周）

- [ ] `gov_reports` 表升级：`+method`（X-Service-Method）、`+payload JSON`、`+batch_date`、`+msg_code`、`+resp_msg`、唯一索引 `(biz_type, biz_id)`。
- [ ] 新增 `backend/app/services/tj_mappers.py`：每个接口一个 `build_xxx(entity) -> dict`，集中维护字段映射（organID/unitID/organName 统一注入；金额分→元两位小数；时间格式 `yyyy-MM-dd HH:mm:ss`；性别/证件/支付渠道等码值转换——paymentChannel 固定 `2` 微信）。
- [ ] 每日采集器（`main.py` 新增 `_tj_daily_collect()`，每日 01:30 北京时间）：
  - 咨询：昨日 `finished_at/cancelled` 终态的 text 订单 → `uploadConsultIndicators`；
  - 复诊：昨日终态 video 订单 → `uploadReferralIndicators`；
  - 电子病历：随复诊订单的处方 EMR → `uploadElectMedicalRecord`；
  - 处方：昨日审方通过处方 → `uploadRecipeIndicators`；
  - 核销：昨日药费支付成功/失效处方 → `uploadRecipeVerificationIndicators`（deliveryType 按实际：0 药房自取 / 1 物流配送）；
  - 评价：昨日新增评价 → `uploadBusinessInfoAfter`；
  - **不良事件：无论有无数据每日必发一次**（空数组签到）→ `pushMedicalDispute`。
- [ ] 事件型上报：药品字典增改 → 即时 enqueue `uploadDrugCatalogue`；患者上传首诊材料 → 即时 `uploadFile` 换取附件 id 存 `orders.first_diagnosis_file_ids`。
- [ ] worker 改造：`compliance_service.process_pending()` 去掉 random 模拟，按 `TJ_REPORT_ENABLED` 分流：关=保持模拟（开发环境），开=调 `tj_gateway.call()`；保留指数退避 `BACKOFF` 与死信；**List 接口整批失败时整批标记 failed 并记录 msg**。
- [ ] 时区注意：服务器为 UTC，"前一天"按北京时间切日（沿用运营后台 UTC→北京时间的换算教训）。

**验收：** 测试环境连续 3 天自动推送成功；平台"接口对接数量"页面各必接接口计数增长；不良事件空签到每日可见。

### S4 · 运营后台监控升级（研发 A，2–3 天）

- [ ] Dashboard 监管面板升级：按 `method` 维度的成功/失败/死信统计；今日签到状态（不良事件是否已签）；失败行展开可看 `payload` 与平台返回 `msg`。
- [ ] 手工操作：单条重报（已有）、**按日期+接口手工补报**（调采集器重跑指定日）。
- [ ] 告警：连续失败 ≥N 或当日签到未完成 → 站内通知/邮件（可复用 notifications）。

**验收：** 人为构造一条必输字段缺失的数据 → 面板可见失败原因（msg 显示缺失字段）→ 补数据后重报成功。

### S5 · 测试达标与切正式（研发 B + C 角，随 M10）

- [ ] 测试环境各必接接口数据量达标（以平台页面为准），通知平台核验。
- [ ] 申请**正式环境**密钥与地址，`.env` 切换，正式环境 IP 白名单。
- [ ] 上线 checklist：`TJ_REPORT_ENABLED=true`；密钥不入库不进 git；`gov_reports` 保留策略；每日 01:30 任务在生产验证一次。
- [ ] 与 M9 其余两项衔接：CA 正式签章（处方 PDF 替换占位章）、OSS 归档 15 年（音视频录制 + 处方 PDF + 上报 payload）。

**验收（= Roadmap M9 上报部分验收）：** 正式环境连续 7 天自动上报成功、失败可在后台重报、不良事件每日签到无遗漏。

---

## 七、风险与决策项

| 风险/决策 | 影响 | 应对 |
| :-- | :-- | :-- |
| ~~SM4 密钥/IV 派生规则规范未写明~~ | ~~S1~~ | ✅ **已消除**：jar 逆向完成，协议细节与黄金向量见 [tianjin_gateway_protocol.md](tianjin_gateway_protocol.md)（注意：规范 PDF 1.1 节文字描述与 SDK 实现不一致，以 SDK 为准） |
| 外包商可能仍以我院 unitID 在正式环境上报；密钥重置时机不当会断报 | S0/S5 | S0 手册 T2 摸底 + T7 切换窗口方案（并行期不动正式密钥，切换日 D 重置，保留回退） |
| 视频问诊按"复诊"上报的口径未经平台确认 | S3 映射 | S0 书面确认；若平台认定为"咨询"则改走 2.2.1，映射层一处切换 |
| 首诊材料/复诊声明改动患者端流程，可能影响转化 | S2 | 产品上做成挂号后补传亦可（复诊接口 firstDiagnosis 非必输），但 referralFlag 必输，声明勾选不可省 |
| 医生/药师身份证等敏感字段收集 | S2 | 沿用 `*_enc` 加密存储与脱敏返回；上报时才解密 |
| List 接口"中途错误整批拒绝" | S3 | 入队前跑 `check_report_ready` 校验必输字段；批量以小批（≤50）提交，失败批可整批重报 |
| 历史存量数据（上线前订单）是否需要补报 | S5 | 与平台确认；如需，用"按日期手工补报"功能回灌 |

---

## 八、与其他文档的关系

- [tianjin_supervision_s0_checklist.md](tianjin_supervision_s0_checklist.md)：S0 阶段详细操作手册（账号收权/摸底/密钥/口径确认/字典对照/切换窗口）。
- [tianjin_gateway_protocol.md](tianjin_gateway_protocol.md)：网关协议实现细则（SDK 逆向确认版，含黄金测试向量），S1 开发与单测依据。
- [backend/scripts/tj_ping.py](../backend/scripts/tj_ping.py)：连通性自检脚本（S0 T4 验收工具，亦是 S1 参考实现）。
- [system_roadmap.md](system_roadmap.md)：M9 的"卫健委实时上报"以本文为准（协议为 SM4/SM3；节奏为每日终态批量推送 + 不良事件每日签到，并非逐单实时）。
- [backend_saas_prd.md](backend_saas_prd.md) §5.1：GovReport 设计沿用，按本文 S3 升级表结构。
- 规范原文及配套资料已归档：[docs/specs/tianjin/](specs/tianjin/)——接口规范（PDF/docx）、官方 SDK jar、《互联网监管平台填报说明》（含机构填报端入口）、国家临床版 2.0 ICD-10 编码表（西医/中医）、中医病证分类与代码、互联网诊疗管理办法。
