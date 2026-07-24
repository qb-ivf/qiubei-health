# 放心签高级证书接口接入说明

> 对齐供应商文档：[ca协议高级证书接口.md](ca协议高级证书接口.md)  
> 实现日期：2026-07-24

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

相关代码：

- `backend/app/services/fxq_ca.py`：token、请求签名、接口调用；
- `backend/app/services/ca_service.py`：人员映射、双录状态机、隐私留存；
- `backend/app/api/v1/ca.py`：医生/药师接口及 H5 回调；
- `backend/app/models/ca_enrollment.py`：双录记录；
- `miniprogram-doctor/pages/ca/`：医师操作入口；
- `admin-web/src/views/CaCertificate.vue`：药师操作入口。

## 2. 重要边界

“高级证书接口”完成的是 CA 协议确认、活体检测和签署意愿核验，**不等同于给处方 PDF 做数字签名**。
所附文档没有以下接口，因此本次没有猜测或伪造实现：

- 个人/企业证书查询及证书 ID；
- 医师签名、药师签名或审核签名；
- 医院企业电子印章；
- PDF 上传、坐标/关键词签署、封存；
- 签后文件下载、签名报告、验签和存证回调。

代码已经删除 `CA_MOCK_SIGN` 和红章占位。未签名 PDF 只显示“开发预览，不可作为有效电子处方”；
当 `FXQ_CA_REQUIRED=true` 时，未完成真实文档签名的 PDF 会拒绝下载。

要完成处方正式签章，仍需放心签补充上述文档及测试参数。

## 3. 环境变量

在服务器环境变量或受保护的 `backend/.env` 中配置，禁止写入 Git：

```dotenv
FXQ_CA_ENABLED=true
FXQ_CA_REQUIRED=false
FXQ_APP_KEY=<开放平台应用 AppKey/AppID>
FXQ_APP_SECRET=<开放平台应用 AppSecret>
FXQ_CA_REDIRECT_URL=https://api.example.com/api/v1/ca/callback
```

四个供应商 URL 已在代码中使用官方默认值，通常不需要覆盖。

- 第一阶段使用 `FXQ_CA_ENABLED=true`、`FXQ_CA_REQUIRED=false`，先让 6 名医师和 4 名药师完成双录。
- 测试环境可以短暂设置 `FXQ_CA_REQUIRED=true` 验证开方/审方门禁；此时未完成双录的医师不能开方，未完成双录的药师不能审方，未完成真实文档签名的 PDF 也会拒绝下载。
- **生产环境必须等 PDF 签署/签后下载/验签接口完成后，才能设置 `FXQ_CA_REQUIRED=true` 并正式启用电子处方。**
- AppSecret 只允许服务端读取，前端接口和日志均不得返回。

## 4. 部署与联调

```bash
cd backend
python -m scripts.migrate
python -m scripts.fxq_ca_preflight
python -m scripts.fxq_ca_preflight --live
```

`--live` 只验证 token，不创建双录订单，也不消耗核验次数。

上线前还需要：

1. 将服务器出口 IP 提交放心签白名单（若该应用启用了 IP 白名单）；
2. 在放心签配置或确认回调地址；
3. 在微信公众平台把 `https://identity.fangxinqian.cn` 配为医生端小程序业务域名；
4. 把 API 域名同时配置为小程序业务域名，使放心签回跳页面可以正常打开；
5. 使用一名测试人员完成：发起 → H5 双录 → 回跳 → 查询结果；
6. 确认数据库只出现元数据，没有身份证明文、照片 Base64 或视频 Base64。

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
