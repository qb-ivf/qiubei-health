# 放心签高级证书接口接入说明

> 对齐供应商文档：[ca协议高级证书接口.md](ca协议高级证书接口.md)  
> 实现日期：2026-07-24
> 生产预检：2026-07-25 已完成配置检查、数据库迁移、正式 token 验证和公网健康检查

## 0. 当前进度

| 项目 | 状态 | 说明 |
| :-- | :-- | :-- |
| 放心签开放平台应用 | ✅ 已完成 | 账号主体迁移已完成，控制台显示天津逑贝互联网医院主体；AppID/AppSecret 已取得，密钥不得写入本文或 Git |
| 已购服务权限 | ✅ 已确认 | 2026-07-23 控制台显示合同签署、核身图片查询、智能鉴证、签章生成、企业四要素、PDF 转图片共 6 项均已开通 |
| 个人数字证书材料 | ✅ 已取得 | 最新回函共 10 人（6 名医师、4 名药师），北京数字认证股份有限公司出具，有效期 2026-03-08 至 2031-03-07 |
| 高级证书接口文档 | ✅ 已取得 | 已覆盖 CA 协议阅读、智能双录发起和结果查询 |
| 双录后端及前端实现 | ✅ 已完成 | 医师小程序、药师后台、回调、轮询、数据库迁移和预检脚本均已实现 |
| PDF 签署/验签接口与代码 | ✅ 已完成 | 已按官方标准 API 实现个人/企业签章生成、三方 PDF 区域签署、合同验签、摘要复核和受保护下载 |
| 官方沙箱端到端 | ✅ 已通过 | 使用官方公开沙箱凭据和虚构主体完成 3 个签章生成 → 三方 PDF 签署 → 合同验签 → 下载，接口均返回 10000，摘要一致 |
| 自动化验证 | ✅ 已完成 | 后端 39 项测试通过，含稳定原文、签章地址白名单、三方验签、摘要不一致拒绝及受保护存储测试 |
| 服务器配置与真实 token 验证 | ✅ 已完成 | 生产 `backend/.env` 配置项齐全；迁移完成；正式 AppKey/AppSecret 换取 token 成功且未输出 token；公网 `/health` 返回 200 |
| 医师/药师真实双录 | ⬜ 待执行 | 先各选 1 人试点，再完成 6 名医师和 4 名药师 |
| 首份真实处方签署 | 🟡 待联调 | 代码、正式密钥和持久卷已部署；仍需确认企业 CA/处方专用章并用 1 名医师 + 1 名药师完成真实签署验收 |

## 1. 已实现范围

当前实现覆盖附件明确给出的“CA 协议阅读 + 智能双录”闭环：

1. 使用开放平台 AppKey/AppSecret 换取 token；
2. 使用放心签官方签名服务，为原始请求体生成 `fxq-nonce` 和 `fxq-sign`；
3. 发起高级证书协议双录，取得两分钟有效的 `agreementUrl`；
4. 医师通过医生端小程序 WebView 完成双录，药师通过运营后台完成双录；
5. H5 回跳后不信任 URL 中的 `code`，后端再次查询放心签结果；
6. 按文档建议最多查询三次、间隔十秒；
7. 保存业务流水、核验 ID、结果、得分和时间，不保存身份证明文、照片或视频；
8. token 失效时自动刷新一次；所有供应商地址限制为放心签官方 HTTPS 域名。

处方文档签署闭环：

1. 用固定 PDF 元数据生成字节稳定的处方原文并计算 SHA-256；
2. 为医师、审核药师生成个人签章，为医院生成“处方专用章”；
3. 将三方主体和固定坐标一次提交至 PDF 区域签署接口；
4. 对签后 URL 立即调用合同验签，逐一核对三方主体、证书有效期、签名和时间戳；
5. 下载签后 PDF，复核其 SHA-256 与放心签验签摘要；
6. 原子写入受保护持久目录；只有此后才把处方置为已审核并允许患者下载。

相关代码：

- `backend/app/services/fxq_ca.py`：token、请求签名、接口调用；
- `backend/app/services/ca_service.py`：人员映射、双录状态机、隐私留存；
- `backend/app/services/fxq_document_service.py`：三方签章、验签、摘要复核和签后文件存储；
- `backend/app/services/prescription_service.py`：审方通过前执行真实签署，失败不改变处方状态；
- `backend/app/api/v1/ca.py`：医生/药师接口及 H5 回调；
- `backend/app/models/ca_enrollment.py`：双录记录；
- `miniprogram-doctor/pages/ca/`：医师操作入口；
- `admin-web/src/views/CaCertificate.vue`：药师操作入口。

## 2. 个人证书材料与文档签署边界

“高级证书接口”完成的是 CA 协议确认、活体检测和签署意愿核验，**不等同于给处方 PDF 做数字签名**。
最新版《个人数字证书》PDF 是 CA 出具的**证书办理情况回函**，用于证明 10 名人员已获发数字证书；
它不是 PFX/P12/X.509 导出文件，也没有放心签 `certId/sealId` 或可供程序直接读取的私钥。

放心签当前标准 API 不要求我方上传私钥或传入 `certId`。签署接口以签署人姓名/企业名称和
身份证号/统一社会信用代码匹配已认证主体，携带 CA 证书完成 PDF 签署。实现已对齐以下官方文档：

- [单文档 PDF 区域签署](https://sign-online-group.oss-cn-hangzhou.aliyuncs.com/sign-open/documentPdf/41.md)；
- [个人/企业签章生成](https://sign-online-group.oss-cn-hangzhou.aliyuncs.com/sign-open/documentPdf/61.md)；
- [合同验签](https://sign-online-group.oss-cn-hangzhou.aliyuncs.com/sign-open/documentPdf/65.md)；
- [获取 token](https://sign-online-group.oss-cn-hangzhou.aliyuncs.com/sign-open/documentPdf/9.md)；
- [请求签名规则](https://sign-online-group.oss-cn-hangzhou.aliyuncs.com/sign-open/documentPdf/81.md)。

系统在药师审方通过时对同一份固定原文一次性加入医师、药师、医院三方签名，随后立即验签；
只有文件未篡改、三方签名及时间戳均有效、下载文件 SHA-256 与放心签验签摘要一致时才落库。
验签记录不保存身份证号、印章图片、印章数据或签名值。

代码已删除 `CA_MOCK_SIGN` 和红章占位。未签名 PDF 只显示“开发预览，不可作为有效电子处方”；
当 `FXQ_CA_REQUIRED=true` 时，未通过真实验签的 PDF 会拒绝下载。

## 3. 环境变量

在服务器环境变量或受保护的 `backend/.env` 中配置，禁止写入 Git：

```dotenv
FXQ_CA_ENABLED=true
FXQ_DOCUMENT_SIGN_ENABLED=false
FXQ_CA_REQUIRED=false
FXQ_APP_KEY=<开放平台应用 AppKey/AppID>
FXQ_APP_SECRET=<开放平台应用 AppSecret>
FXQ_CA_REDIRECT_URL=https://api.example.com/api/v1/ca/callback
FXQ_COMPANY_NAME=天津逑贝互联网医院有限公司
FXQ_COMPANY_IDNO=<统一社会信用代码>
FXQ_SIGNED_PDF_DIR=/app/storage/prescriptions
```

供应商 URL 已在代码中使用官方默认值，通常不需要覆盖。

- 第一阶段使用 `FXQ_CA_ENABLED=true`、`FXQ_DOCUMENT_SIGN_ENABLED=false`、
  `FXQ_CA_REQUIRED=false`，先让 6 名医师和 4 名药师完成双录。
- 首份处方联调时设置 `FXQ_DOCUMENT_SIGN_ENABLED=true`、`FXQ_CA_REQUIRED=false`；
  此时审方会真实消耗 3 次签章生成和 1 次合同签署额度，失败则处方保持待审。
- 首份三方签署、验签、下载及备份均验收后，生产设置 `FXQ_CA_REQUIRED=true`；
  此时未完成双录的医师不能开方，未完成双录的药师不能审方，未通过验签的 PDF 不能下载。
- AppSecret 只允许服务端读取，前端接口和日志均不得返回。
- `FXQ_SIGNED_PDF_DIR` 必须放在持久卷并纳入加密备份；默认本地目录仅适用于开发联调。

## 4. 部署与联调

```bash
cd backend
python -m scripts.migrate
python -m scripts.fxq_ca_preflight
python -m scripts.fxq_ca_preflight --live
```

`--live` 只验证 token，不创建双录订单，也不消耗核验次数。

`backend/docker-compose.yml` 已把 `prescription_data` 持久卷挂到 `/app/storage/prescriptions`；
非容器部署可改为 `/data/qiubei/prescriptions`。目录仅允许 API 运行账号读写，不得通过 Nginx 静态暴露。
处方下载必须经过 `/api/v1/prescriptions/{order_id}/pdf` 的登录和归属校验。

上线前还需要：

1. 将服务器出口 IP 提交放心签白名单（若该应用启用了 IP 白名单）；
2. 在放心签配置或确认回调地址；
3. 在微信公众平台把 `https://identity.fangxinqian.cn` 配为医生端小程序业务域名；
4. 把 API 域名同时配置为小程序业务域名，使放心签回跳页面可以正常打开；
5. 使用一名测试人员完成：发起 → H5 双录 → 回跳 → 查询结果；
6. 确认数据库只出现脱敏证书元数据，没有身份证明文、照片/视频 Base64、印章图片或签名值；
7. 使用脱敏测试处方完成三方签署，核对验签签名数为 3，篡改签后 PDF 后本地摘要校验必须拒绝下载。

## 5. 本系统接口

| 方法 | 地址 | 用途 |
| :-- | :-- | :-- |
| GET | `/api/v1/ca/config` | 查看是否启用及非敏感配置检查结果 |
| GET | `/api/v1/ca/enrollments/latest` | 查看本人最近一次双录 |
| POST | `/api/v1/ca/enrollments` | 发起或复用两分钟内的双录链接 |
| POST | `/api/v1/ca/enrollments/{orderNo}/refresh` | 服务端查询核验结果 |
| GET | `/api/v1/ca/callback` | 放心签 H5 回跳；公开但不信任回跳成功码 |

只有医师和药师本人可以发起、查看自己的双录记录。管理员不能代替药师完成双录；生产强制模式下，
管理员也不能代替药师通过处方。

## 6. 下一步操作清单

> 按顺序执行。任何 AppSecret、token、身份证号、照片或视频均不得粘贴到本文、Git、工单截图或聊天记录。

### A. 服务器配置与连通性

- [x] A0. 放心签账号主体已由原主体迁移为天津逑贝互联网医院主体（2026-07-23/24 确认）；
- [x] A1. 已在生产服务器受保护的 `backend/.env` 配置（2026-07-25）：
      `FXQ_APP_KEY`、`FXQ_APP_SECRET`、`FXQ_CA_REDIRECT_URL`、
      `FXQ_COMPANY_NAME`、`FXQ_COMPANY_IDNO`、`FXQ_SIGNED_PDF_DIR`；
- [ ] A2. 设置 `FXQ_CA_ENABLED=true`，先保持
      `FXQ_DOCUMENT_SIGN_ENABLED=false`、`FXQ_CA_REQUIRED=false`；
- [ ] A3. 确认 `FXQ_CA_REDIRECT_URL` 是公网可访问的 HTTPS 地址，路径为
      `/api/v1/ca/callback`；
- [x] A4. 控制台已确认合同签署、核身图片查询、智能鉴证、签章生成、企业四要素、
      PDF 转图片共 6 项服务已开通；
- [ ] A4.1. 向放心签确认生产服务器出口 IP 是否需要加入白名单；
- [x] A5. 已在生产容器执行 `python -m scripts.migrate`（2026-07-25），
      `ca_enrollments` 表已存在，处方签署/验签字段已创建；
- [x] A6. 已执行 `python -m scripts.fxq_ca_preflight`，配置与官方域名检查全部为 `OK`；
- [x] A7. 已执行 `python -m scripts.fxq_ca_preflight --live`，正式
      AppKey/AppSecret 换取 token 成功，输出中未出现 token；
- [ ] A8. 调用 `GET /api/v1/ca/config`，确认 `enabled=true`、`ready=true`、`errors=[]`。
- [ ] A9. Compose `prescription_data` 持久卷已于 2026-07-25 创建；仍需
      限制为 API 账号读写并验证备份/恢复，
      禁止静态公开访问。

### B. 小程序与回调域名

- [ ] B1. 在医生端微信小程序后台配置 `https://identity.fangxinqian.cn` 为业务域名；
- [ ] B2. 把我方 API HTTPS 域名配置为业务域名，保证 H5 可以回跳；
- [ ] B3. 若微信要求校验文件，按公众平台提示部署校验文件并完成验证；
- [ ] B4. 真机打开“工作台 → CA数字证书”，确认放心签 H5 可正常加载；
- [ ] B5. 验证 H5 完成后能回到我方回调页，并能返回医生端查询结果。

### C. 首轮真实联调

- [ ] C1. 选择 1 名医师本人完成：发起 → 阅读协议 → 人脸活体 → 意愿回答 → 回跳；
- [ ] C2. 选择 1 名药师本人在运营后台完成同样流程；
- [ ] C3. 核对两人的最新记录均为 `succeeded`，`faceCode=0`；
- [ ] C4. 核对数据库仅保存流水号、核验 ID、状态、得分和时间，
      不存在身份证明文、照片 Base64、视频 Base64；
- [ ] C5. 测试失败、主动退出、两分钟链接过期和重新发起；
- [ ] C6. 测试结果异步延迟场景，确认按 10 秒间隔最多查询 3 次；
- [ ] C7. 留存脱敏后的请求时间、业务流水和结果截图作为联调证据。

### D. 完成全部人员双录

- [ ] D1. 其余 5 名医师本人完成双录，最终医师进度达到 **6/6**；
- [ ] D2. 其余 3 名药师本人完成双录，最终药师进度达到 **4/4**；
- [ ] D3. 逐人核对姓名、岗位及系统账号映射，禁止共用账号或由管理员代办；
- [ ] D4. 建立证书/双录到期提醒；接口套餐当前有效期与人员证书有效期不一致时，
      以较早到期日提前 30 天告警；
- [ ] D5. 测试环境可短暂设置 `FXQ_CA_REQUIRED=true`，验证未双录医师不能开方、
      未双录药师不能审方；验证后恢复为 `false`。

### E. 正式处方签章资料与权限

- [x] E1. 放心签开放平台账号主体迁移完成，控制台已显示天津逑贝互联网医院主体；
- [x] E2. 取得北京数字认证股份有限公司最新个人数字证书办理回函：
      6 名医师 + 4 名药师，有效期 2026-03-08 至 2031-03-07；
- [x] E3. 确认当前标准签署 API 按姓名/证件号匹配认证主体，不要求我方传
      `certId/userId` 或上传私钥；
- [x] E4. 已取得个人/企业签章生成、PDF 区域签署、签后 URL 和合同验签官方接口文档；
- [x] E5. 控制台已开通“合同签署”和“签章生成”正式服务额度；
- [ ] E6. 向放心签确认医院企业 CA 证书及“处方专用章”是否已完成认证并可用于正式签署；
- [ ] E7. 确认接口限流、请求超时后的计费/重试规则，以及重复请求是否提供幂等键；
- [ ] E8. 确认签后文件/签署证据的法定保存方案和可选存证服务；当前应用未显示存证服务额度。

建议向放心签明确说明目标顺序：

```text
医师对处方原文签名
→ 药师审核并电子签名或形成可验证审核留痕
→ 天津逑贝互联网医院有限公司加盖企业电子印章
→ 文件封存
→ 下载签后 PDF、签署报告并验签
→ OSS 合规归档
```

### F. 正式处方签章开发与上线

- [x] F1. 已实现姓名/身份证密文和企业主体的安全映射；身份证仅在调用时短暂解密；
- [x] F2. 已实现原始处方 SHA-256、医师/药师/医院三方区域签署；
- [ ] F3. 已用数据库行锁防止同一处方并发审方；仍需结合放心签答复补充供应商幂等键、
      超时状态查询/人工补偿（标准签署接口为同步响应，无签署回调）；
- [x] F4. 已实现签后 PDF 下载、三方证书/时间戳验签及下载文件摘要复核，
      只有全部通过才标记 `verified`；
- [ ] F5. 已实现受保护本地持久目录和登录归属校验下载；生产仍需挂载持久卷，
      接入 OSS/对象锁与长期备份策略；
- [ ] F6. 已完成摘要不一致、非官方地址、签名缺失和路径越界自动化测试；
      真实环境还需补证书过期、供应商超时和余额不足演练；
- [ ] F7. 医务、药事、法务共同验收一份完整样例处方；
- [ ] F8. 首份真实联调设置 `FXQ_DOCUMENT_SIGN_ENABLED=true`；验收后生产再设置
      `FXQ_CA_REQUIRED=true`，确认未签名 PDF 返回 409，
      只有验签成功的处方可以下载和流转；
- [ ] F9. 连续观察至少 3 个工作日，无漏签、错签、重复签署及敏感信息泄漏后转入稳态。

## 7. 最终验收标准

以下条件全部满足，CA 电子处方签章才可标记为完成：

- [ ] 6 名医师、4 名药师均有本人可验证的 CA 身份及签章映射；
- [ ] 医师、药师、医院三方主体与签章证书中的主体一致；
- [ ] 任意一份签后处方均能验证原文未篡改、签名有效、证书有效、时间戳有效；
- [ ] 处方修改或驳回重开后，旧签名自动失效并重新走完整签署流程；
- [ ] 签后 PDF、签署报告、验签结果和操作审计可以按处方号完整追溯；
- [ ] 前端、日志、数据库和 Git 中不存在 AppSecret、token、身份证明文及生物识别文件；
- [ ] `CA_MOCK_SIGN`、图片章冒充签名及“未签先流转”路径全部不存在。
