# 天津市互联网诊疗监管平台对接实施方案（M9 落地版）

> 依据：《天津市互联网医院自建平台数据监管接口规范 ver1.0》（2025-04-23 修订，下称"规范"）。
> 本文替代 [system_roadmap.md](system_roadmap.md) 中 M9 关于卫健委上报的旧假设（原文按 AES-128-CBC + MD5 动态 Sign 预估，**实际规范为 SM4-CBC 加密 + SM3 签名的国密网关**），并给出按阶段的实施计划。
>
> 现状基线：MVP（M1–M6）与 M7/M8 大部分已实现；监管上报仅有**占位框架**（`gov_reports` 表 + 模拟 sweeper + admin 监控面板），未接真实网关。

---

## 〇、进度快照（2026-07-24 更新）

| 阶段 | 状态 | 说明 |
| :-- | :-: | :-- |
| **协议逆向** | ✅ 完成 | SM4-CBC/SM3/签名规则确认，黄金向量固化 |
| **S1 国密网关客户端** | ✅ 完成 | `tj_gateway`/`sm_crypto`，单测 7 全绿 |
| **S2 数据模型与业务补齐** | ✅ 完成 | 3 新表 + 全部补列 + 评价/不良事件/复诊声明/ICD/首诊材料，两端小程序改造完毕 |
| **S3 上报映射与调度** | ✅ 完成 | 9 接口 mapper + 每日采集器 + 退避重试 + 按日补采 |
| **S4 运营后台监控** | ✅ 基本完成 | 按接口统计/看报文/按日补采；仅"告警阈值"待联调后定 |
| **S5 测试联调** | 🟡 待正式首批 | 测试冒烟 **9/9 msgCode=200**、反显及历史达标沿用均确认；正式密钥已发放并在本地安全暂存，余：T6 补录、生产预检/部署、首批核验 |
| **代码整体** | ✅ 完成 | 27 tests passed；新增正式只读预检、目录初始化、生产防误写/防吞队列及药师备案入口 |

> **一句话**：测试联调和正式密钥均已到位；现在只差在生产库完成 T6 人员/药品补录，通过
> `tj_preflight.py` 后初始化真实药品目录并开启上报。远程会诊没有实际业务，仍不生成生产数据。

---

## 一、对照 Roadmap 的未完成工作总览

| 里程碑 | 状态 | 未完成项 |
| :-- | :-: | :-- |
| M1–M6（MVP 闭环） | ✅ 基本完成 | 微信支付已上线（生产），无阻塞项 |
| M7 履约与通知 | 🟡 80% | 物流时间轴为演示数据；订阅消息模板未接正式 |
| M8 运营后台 | 🟡 95% | 提现"商家转账到零钱"打款未接真实；其余已完成 |
| **M9 合规网关硬化** | 🟢 **监管上报≈95%** | 代码、测试联调、正式密钥均完成；余 T6 补录与正式首批。CA 三方签章/验签代码已完成，余真实首单与长期归档 |
| M10 提审上线 | ⬜ 0% | 医生端正式 AppID 未申请；两端提审、等保自查 |
| 并行轨道 | 🟢 | 监管平台测试/正式密钥✅到手；放心签主体迁移和 6 项服务权限✅，余 CA 真实首单；医疗类目资质仍待办 |

M9 内部三件事的优先级：**① 监管上报（本文，卡上线）→ ② CA 正式签章（处方合法性）→ ③ 音视频/处方 15 年归档**。

---

## 二、规范要点速读（协议层）

1. **准入**：向监管平台申请 `unitId`、`appKey`、`appSecret` 与服务权限。规范列有 40007（IP 非法），但平台 T5 书面确认当前测试/正式均**不设 IP 白名单**，以密钥验权。两套地址与密钥在"申请子系统 → 技术对接 → 秘钥生成及管理"查看。
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

4. **签名**：`sign = SM3(拼接串)`。参与签名的头按 key 字典序，以 `小写头名:值` 和 `&` 拼接；密文不直接进入签名串，由 `X-Content-MD5=SM3(密文)` 间接绑定。
5. **返回**：外层 `code`（HTTP 层：200 成功；40001 参数错、40004 密钥不匹配、40007 IP 非法、40010 签名不合法、40011 请求过期…），内层 `body.msgCode`（业务层：200 成功；-99 字段为空，msg 用 `|` 列出字段；-98 数据为空；-1 具体失败文案）。**List 型接口中途出错即整批返回错误**，需按批重报。
6. **附件上传**：规范曾列 `api/uploadFile`，但平台 T5 书面确认当前**没有该接口**；我方不外发本地附件路径，`firstDiagnosis` 留空且测试已通过。
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
| 2 | 2.1.3 附件上传 | `uploadFile`（`api/uploadFile`） | ❌ 平台未开放 | T5 书面答复确认无该接口；首诊材料仍在院内留存，监管 `firstDiagnosis` 留空（测试已通过） |
| 3 | 2.2.1 在线咨询 | `uploadConsultIndicators` | ✅ 必接 | `consult_type=text` 图文咨询订单（终态：完成/取消） |
| 4 | 2.2.2 在线复诊 | `uploadReferralIndicators` | ✅ 必接 | `consult_type=video` 视频问诊订单（互联网医院只允许复诊，视频问诊按复诊上报） |
| 5 | 2.2.10 电子病历 | `uploadElectMedicalRecord` | ✅ 必接 | `prescriptions` 表 EMR 部分，随复诊 |
| 6 | 2.2.3 在线处方 | `uploadRecipeIndicators` | ✅ 必接 | 审方通过的处方（前一天开具） |
| 7 | 2.2.4 处方核销 | `uploadRecipeVerificationIndicators` | ✅ 必接 | 药费支付成功/处方失效（前一天核销） |
| 8 | 2.4.1 评价信息 | `uploadBusinessInfoAfter` | ✅ 必接（强制，不分业务） | **新增**评价功能 |
| 9 | 2.4.2 医疗争议（不良事件） | `pushMedicalDispute` | ✅ 必接（强制 + **每日签到**） | **新增**不良事件登记 |
| 10 | 2.2.9 预约挂号 | `uploadAppointRecord` | ✅ 必接（平台反显页确认，2026-07-03） | 支付成功的挂号单（含其后取消的），T+1 批量 |
| 11 | 2.1.2 护理耗材目录 / 2.2.5–2.2.8 互联网护理 | — | ❌ 不适用 | 平台反显页标记"不需要对接"，与判断一致 |
| 12 | 2.3.1/2.3.3–2.3.6 远程医疗（门诊/影像/心电/病理/转诊） | — | ❌ 不适用 | 平台反显页标记"不需要对接" |
| 13 | 2.3.2 远程会诊 | `uploadMeetClinicIndicators` | 🟡 保留但暂不上报 | 平台标记"需要对接"，我院无此业务（外包商误勾）。2026-07-04 决定保留勾选、暂不开发；真要报再补 mapper（半天）。详见 S0 手册 |

---

## 四、差距分析（现状 vs 规范）

> ⚠️ **本节为立项时（未实现前）的基线诊断，仅作历史记录。** 下列缺口 S1–S3 已全部补齐（协议层、数据字段、业务功能均完成），当前实际状态以〇进度快照与六阶段计划的勾选为准。

### 4.1 协议层（~~全部缺失~~ → ✅ 已补齐）
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
gov_reports（升级：+method +payload +batch_date +msg_code；应用层按 biz_type/biz_id 幂等）
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
- 幂等：应用层按 `(biz_type, biz_id)` 查询复用，复合索引加速；终态才入队，重复入队直接忽略。

---

## 六、分阶段实施计划

> 建议节奏：S0 立即启动（非研发阻塞项），S1–S4 为研发主线（约 3–4 周），S5 联调转正式。每阶段有明确验收，通过再进下一阶段。

### S0 · 前置准备（并行，负责人：C 角/项目负责人，本周启动）

> 详细操作步骤已展开为独立手册：**[tianjin_supervision_s0_checklist.md](tianjin_supervision_s0_checklist.md)**（含账号收权、外包商存量上报摸底、切换窗口方案——我院 2023 年已持牌、此前由外包商代报，S0 核心是收权而非新入驻）。

任务概览（细节见手册）：

| # | 任务 | 状态 |
| :-: | :-- | :-: |
| T1 | 监管平台机构账号收权（入口 `imssp.wsjk.tj.gov.cn`），改密 | 🟡 已可登录并操作；余：改密 |
| T2 | 摸底外包商存量上报现状 | ✅ 关闭：正式环境零上报，外包商仅 2025-08 测试刷数达标，从零接入 |
| T3 | 测试/正式密钥 + 方法权限 + IP 白名单 | ✅ 两套密钥均到手；实测无 40006/40007；正式凭据已在本地 `.env` 暂存且开关关闭 |
| T4 | 首次连通性验证 `tj_ping.py` | ✅ 完成（2026-07-04 生产容器内）：`msgCode=200` |
| T5 | 口径书面确认 | ✅ 2026-07-07 全部书面回签，见 [T5-口径确认函](specs/tianjin/T5-口径确认函-待发平台.md) |
| T6 | 字典对照 + 名册录入 | 🟡 字典 CSV/模板全备、医生名册草稿已取得；余：admin 录入 10 人 + 药房填药品对照 |
| T7 | organID 核对 + 上线方案 | 🟡 organID、正式凭据✅；余生产预检/首次目录/首批核验 |
| — | ~~下载 Java SDK 并对拍加密/签名规则~~ | ✅ 已完成 |
| — | 九接口联调冒烟 `tj_smoke.py` | ✅ **9/9 msgCode=200**（2026-07-04）+ 平台反显计数核对通过 |

✅ **协议已提前确认**：官方 jar 已到手并完成逆向对拍，SM4-CBC（appSecret 为 32 位 hex 密钥、固定 IV）、SM3 签名（TreeMap 字典序 + `小写头名:值` + `&` 连接）、X-Content-MD5 实为 SM3 等全部细节及**黄金测试向量**已固化在 **[tianjin_gateway_protocol.md](tianjin_gateway_protocol.md)**——S1 最大不确定项已消除。

**验收：** 见手册末尾 DoD 清单；核心是 `tj_ping.py` 对测试网关返回 `msgCode=200`。

### S1 · 国密网关客户端（研发 B，协议已确认，压缩为约 2 天）

新增 `backend/app/services/tj_gateway.py` + `backend/app/utils/sm_crypto.py`，**实现细则与对拍向量见 [tianjin_gateway_protocol.md](tianjin_gateway_protocol.md)**（`tj_ping.py` 中的 `sm3_hex_upper/sm4_encrypt_hex/build_headers` 三个函数即为参考实现，搬入正式模块即可）：

- [x] `requirements.txt` 增加 `gmssl`。
- [x] `sm_crypto.py`：SM4-CBC（key=hex 解码的 appSecret，IV 固定 `abcd0863…`，**ISO7816-4 填充**——实测非 PKCS7，输出小写 hex）；SM3（输出转大写）。
- [x] `tj_gateway.py`：
  - `build_sign_headers(...)`：按协议文档第一节组装（requestBody 不进签名串，经 X-Content-MD5 间接绑定）；
  - `tj_call(method, payload) -> TjResult`：POST 密文本体；`code=-1/40011/超时/5xx` 可重试，`-99/-98/40001/业务-1` 为数据错误（不自动重试，进失败列表待人工）；
  - `tj_upload_file(...)`：按旧规范保留但无调用方；平台已确认当前未开放 uploadFile。
- [x] `config.py`/`.env` 新增：`TJ_GATEWAY_URL`、`TJ_APP_KEY`、`TJ_APP_SECRET`、`TJ_UNIT_ID`、`ORGAN_ID`、`ORGAN_NAME`、`TJ_REPORT_ENABLED`（开关，默认 false 保持现状占位）。
- [x] 单元测试 `tests/test_tj_gateway.py`：黄金向量 V1–V9 全部断言，**7 passed** ✅。
- [x] 拿到测试密钥后 `tj_ping.py` 打真实网关：**`msgCode=200`（2026-07-04）** ✅。

**验收：** ✅ **全部达成**——单测 V1–V9 全绿 + 测试环境真密钥调用 `uploadDrugCatalogue` 返回 `msgCode=200`。

### S2 · 数据模型与业务功能补齐（研发 B + A，约 1 周）

后端（`scripts/migrate.py` 补列 + 模型修改）：

- [x] `orders` 加列：paid_at/accepted_at/finished_at/cancel_reason/wx_transaction_id/**wx_drug_transaction_id**（挂号与药费流水分开存）/referral_flag/original_diagnosis/first_diagnosis_file_ids；`prescriptions` 加 icd_code/icd_name。migrate.py 已同步。
- [x] 其余表加列（migrate.py 已含全部）：`doctors`（id_card_enc/subject_code/subject_name/dept_code）、`staff`（id_card_enc）、`patients`（cert_type/guardian_*）、`prescriptions`（recipe_unique_id/checked_at/audit_staff_id）、`drugs`（drug_class/countrydrcode/packing/manufacturer/use_flag）。**列已建，字段值待 S0 T6 录入。**
- [x] 状态机埋时间戳：支付回调写 `paid_at`+微信流水号（真实回调透传 `transaction_id`）；接诊 `1→2` 写 `accepted_at`；FINISHED/REFUNDED/CANCELLED 写 `finished_at`；超时取消/退款写 `cancel_reason`。集中在 `order_service._stamp()`，幂等只写首次。
- [x] 新表 `icd10_codes`（west 35862 条 + tcm 1890 条）+ 导入脚本 `scripts/import_icd10.py`（幂等，`--force` 重导，直接读归档 xlsx）。
- [x] 新表 `evaluations`（一单一评，含满意度 1-5/评分 0-10/内容/投诉建议）+ 患者端 API `POST/GET /orders/{id}/evaluation`（完成或退款后可评，创建即入监管上报队列）+ admin 只读列表。
- [x] 新表 `medical_disputes` + admin 登记/编辑接口（合规记录不提供删除）+ admin-web「不良事件登记」「患者评价」页面（监管合规菜单组，构建通过）。
- [x] 开方接口：`PrescriptionCreate` 接受 `icd_code/icd_name`（多个 `|` 分隔）落库；搜索接口 `GET /api/v1/icd10?q=`（编码前缀/名称模糊，west/tcm/all）。
- [x] 开方 items 扩展字段（drug_id/frequency/dosage/drunit/dose_unit/use_days）：schema 已加，医生端表单已收集用药天数/频度，mapper 对缺省有安全兜底（冒烟 9/9 验证）。

前端：

- [x] **患者端小程序**：医生详情页（视频问诊）新增"复诊声明"卡——声明勾选（不勾选不可支付）+ 首诊诊断填写 + 首诊材料拍照上传（≤4 张，支付成功后自动上传）；新增「问诊评价」页（星级 1–5 + 0–10 分滑条 + 内容/建议），订单列表完成/退款单显示"评价"入口，已评价只读回显。
- [x] **医生端小程序**：开方页诊断改 **ICD-10 搜索多选**（chips，选中自动同步诊断文字，提交带 `icd_code/icd_name`）；药品搜索从内置演示库切换为**后端药品字典**（带 drug_id/限售拦截提示）；处方明细新增**用药天数**步进器；病历页顶部展示患者复诊声明 + 首诊材料图（可预览）。
- [x] **admin-web**：新增「不良事件登记」（全字段表单 + 编辑）与「患者评价」（只读）页面，挂在"监管合规"菜单组。
- [x] **admin-web**：医生、药师身份证（加密不回显）及医生科目/科室编码、药品监管字段均有录入口与"监管备案"状态；未备案审方账号会被拦截。实际值仍待 S0 T6 录入。

**验收：** ✅ 测试网关 `tj_smoke.py` **9/9 msgCode=200**；正式切换另由只读
`scripts/tj_preflight.py` 校验生产库的人员、药品、密钥和队列状态。

### S3 · 上报映射与调度（研发 B）——✅ 代码完成，测试联调已通过

- [x] `gov_reports` 表升级：`+method`、`+payload JSON`（入队时快照，可审计可重报）、`+batch_date`、`+msg_code`、`+resp_msg`、`+next_retry_at`、复合索引 `(biz_type, biz_id)`（幂等由 `enqueue` 应用层保证，`refresh=True` 支持目录更新/签到覆盖）。
- [x] `tj_mappers.py`：8 个接口的 `build_xxx(entity) -> dict` 纯函数映射（机构三要素统一注入；分→元；naive UTC→北京时间字符串；性别/证件/支付渠道码值转换；密文字段仅在 payload 中解密；缺数据字段输出空串由平台 -99 指认）。单测覆盖（tests/test_tj_mappers.py）。
- [x] 每日采集器 `tj_collector.collect_daily()`（`main.py` `_tj_daily_collect()` 每日北京时间 01:30）：终态订单（图文→咨询 / 视频→复诊+电子病历，**未支付即取消的不上报**）、审方通过处方、药费核销、新增评价、**不良事件每日签到（空数组也发）**。北京时间切日。
- [x] 事件型上报：admin 药品增/改/删 → 即时 enqueue `uploadDrugCatalogue`（删除→useFlag=2 取消）。
- [x] 患者上传首诊材料继续院内留存；平台确认没有 `uploadFile`，采集器不再尝试上传，本地路径绝不外发。
- [x] worker：`DEBUG=true` 且开关关闭时保留本地模拟闭环；**生产开关关闭时任务保持 pending，不再伪装成功**。配置完整且开关开启才真实发送；药品目录优先于业务队列，网络错误退避重试、数据错误进死信。
- [x] 手工按日补采：`POST /admin/gov-reports/collect {"day":"YYYY-MM-DD"}`（幂等，可回灌历史）。
- [x] 审方链路补齐：审方通过时生成 `recipe_unique_id`、记录 `checked_at` 与审方药师 `audit_staff_id`。
- [x] 旧占位 enqueue（接诊/审方即时入队）已移除，统一走 T+1 批量。

**验收：** ✅ 测试网关九接口冒烟 9/9 通过、平台"测试接口双向反显"计数精确 +1 核对一致（2026-07-04）。剩余"正式环境连续多日自动推送"随 S5 切正式后验证。

### S4 · 运营后台监控升级（研发 A）——✅ 基本完成

- [x] Dashboard 监管面板升级：按 `method` 维度的总数/成功/待发/失败统计表；真实上报启用状态徽标；最近一次不良事件签到状态；失败行"看报文"（payload 快照 JSON）与失败原因（含平台 msg）。
- [x] 手工操作：单条重报（已有）、**按日补采**（日期选择器 + `POST /admin/gov-reports/collect`，幂等可回灌历史）。
- [ ] 告警：连续失败 ≥N 或当日签到未完成 → 站内通知/邮件（可复用 notifications，联调期观察后再定阈值）。

**验收：** 人为构造一条必输字段缺失的数据 → 面板可见失败原因（msg 显示缺失字段）→ 补数据后重报成功（待 S0 密钥联调时执行）。

### S5 · 测试达标与切正式（研发 B + C 角，随 M10）

- [x] 九接口测试联调打通（tj_smoke 9/9 + 反显核对）——核心达标已过。
- [x] 达标数量：T5 确认历史达标可沿用，无需重刷。
- [x] 正式地址与 appKey/appSecret 已发放；本地 `.env` 已切正式凭据但保持 `TJ_REPORT_ENABLED=false`，凭据不入 git。
- [ ] 生产上线：完成 T6 → `tj_preflight.py` 零 FAIL → `tj_bootstrap_drugs.py` 首次目录入队 → 开启上报并重启 → 核验目录及次日 01:30 批次。
- [ ] 与 M9 其余两项衔接：CA 三方签章/验签代码已完成，待正式账户首单；OSS 归档 15 年
      （音视频录制 + 签后处方 PDF + 上报 payload）仍待实施。

**验收（= Roadmap M9 上报部分验收）：** 正式环境连续多日自动上报成功、失败可在后台重报、不良事件每日签到无遗漏。

---

## 七、风险与决策项

| 风险/决策 | 影响 | 应对 |
| :-- | :-- | :-- |
| ~~SM4 密钥/IV 派生规则规范未写明~~ | ~~S1~~ | ✅ **已消除**：jar 逆向完成，协议细节与黄金向量见 [tianjin_gateway_protocol.md](tianjin_gateway_protocol.md)（注意：规范 PDF 1.1 节文字描述与 SDK 实现不一致，以 SDK 为准） |
| ~~外包商可能仍在正式上报~~ | ~~S0/S5~~ | ✅ T2 已确认正式环境历史为零，不存在并行上报或切换断报 |
| 视频问诊按"复诊"上报的口径未经平台确认 | S3 映射 | S0 书面确认；若平台认定为"咨询"则改走 2.2.1，映射层一处切换 |
| 首诊材料/复诊声明改动患者端流程，可能影响转化 | S2 | 产品上做成挂号后补传亦可（复诊接口 firstDiagnosis 非必输），但 referralFlag 必输，声明勾选不可省 |
| 医生/药师身份证等敏感字段收集 | S2 | 沿用 `*_enc` 加密存储与脱敏返回；上报时才解密 |
| List 接口"中途错误整批拒绝" | S3 | 正式前跑 `tj_preflight.py`；运行期按单业务任务/小批发送，失败可独立重报 |
| ~~历史存量数据是否需补报~~ | ~~S5~~ | ✅ **已释除**：我院从未实际开展互联网诊疗业务、正式环境零上报，无存量数据需补报（T5 Q12 改为陈述立场）。上线时"先开开关再放患者"即无缝 |
| 外包商已刷测试达标、我方换自建平台，达标能否沿用 | S5 | T5 Q3 确认；不沿用则 `tj_smoke.py --count 50` 一键刷满 |

---

## 八、与其他文档的关系

- [tianjin_supervision_s0_checklist.md](tianjin_supervision_s0_checklist.md)：S0 阶段详细操作手册（账号收权/摸底/密钥/口径确认/字典对照/切换窗口）。
- [tianjin_gateway_protocol.md](tianjin_gateway_protocol.md)：网关协议实现细则（SDK 逆向确认版，含黄金测试向量），S1 开发与单测依据。
- [backend/scripts/tj_ping.py](../backend/scripts/tj_ping.py)：连通性自检脚本（S0 T4 验收工具，亦是 S1 参考实现）。
- [backend/scripts/tj_preflight.py](../backend/scripts/tj_preflight.py)：正式切换只读预检（不写库、不请求平台）。
- [backend/scripts/tj_bootstrap_drugs.py](../backend/scripts/tj_bootstrap_drugs.py)：正式首次药品目录安全入队（默认仅预览）。
- [system_roadmap.md](system_roadmap.md)：M9 的"卫健委实时上报"以本文为准（协议为 SM4/SM3；节奏为每日终态批量推送 + 不良事件每日签到，并非逐单实时）。
- [backend_saas_prd.md](backend_saas_prd.md) §5.1：GovReport 设计沿用，按本文 S3 升级表结构。
- 规范原文及配套资料已归档：[docs/specs/tianjin/](specs/tianjin/)——接口规范（PDF/docx）、官方 SDK jar、《互联网监管平台填报说明》（含机构填报端入口）、国家临床版 2.0 ICD-10 编码表（西医/中医）、中医病证分类与代码、互联网诊疗管理办法。
