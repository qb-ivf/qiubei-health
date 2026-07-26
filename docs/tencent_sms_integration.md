# 腾讯云短信接入与生产验收

> 更新日期：2026-07-26。本文只记录非敏感的平台编号和操作步骤；`SecretId`、`SecretKey`
> 只能保存在生产服务器 `backend/.env`，不得提交 Git、截图或发送到聊天中。

## 1. 腾讯云控制台现状

| 项目 | 控制台信息 | 当前状态 | 系统用途 |
| --- | --- | --- | --- |
| 实名资质 | ID `1298330`，天津逑贝互联网医院 | 已通过 | 短信签名归属资质 |
| 短信签名 | ID `706643`，`天津逑贝互联网医院` | 可用（正常）、已生效 | `TENCENT_SMS_SIGN` |
| 手机注册 | 模板 ID `2695131`，参数 `{1}` 验证码、`{2}` 有效分钟数 | 已生效 | 患者新增就诊人手机号 |
| 修改注册手机号 | 模板 ID `2695133`，参数 `{1}` 验证码 | 已生效 | 患者修改就诊人手机号 |
| 密码重置 | 模板 ID `2695132` | 已生效 | 暂不接入：当前没有短信密码重置流程 |
| 登录验证码 | 模板 ID `2695129` | 已生效 | 暂不接入：两端当前使用微信登录 |

2026-07-26 已确认 4 个模板全部生效；当前接入使用的 `2695131`、`2695133` 已具备真机
发送条件。

## 2. 已完成的代码对齐

- `SendSms` 使用腾讯云当前 `2021-01-11` API，并按业务用途选择模板和参数顺序。
- 患者端新增就诊人发送 `register_phone`，对应 `2695131` 和参数
  `[验证码, "5"]`；编辑手机号发送 `change_phone`，对应 `2695133` 和参数
  `[验证码]`。
- 短信接口要求有效患者登录态，旧版患者端未传 `purpose` 时暂按注册模板兼容。
- 验证码使用密码学安全随机数，只在腾讯云接受发送后写入 Redis，5 分钟有效且成功校验后立即失效。
- Redis 键不保存手机号或 IP 明文；同手机号至少间隔 60 秒、自然日最多 2 次，同账号每小时
  最多 5 次、同 IP 每小时最多 30 次。服务商拒绝或网络失败时不会留下可验证的“未发送验证码”。
- 生产配置不完整时继续 fail-closed，不回传开发验证码；日志不记录手机号、验证码或腾讯云密钥。

## 3. 生产服务器配置

先从腾讯云“短信 > 应用管理”取得该短信应用的 `SDKAppID`，并准备专用访问密钥。不要把
`AppID`、腾讯云账号 ID 或放心签 AppID 误填为短信 `SDKAppID`。

在生产服务器执行：

```bash
cd /opt/qiubei-health/backend
nano .env
```

补齐或替换以下项目：

```dotenv
TENCENT_SMS_SECRET_ID=<腾讯云访问密钥 SecretId>
TENCENT_SMS_SECRET_KEY=<腾讯云访问密钥 SecretKey>
TENCENT_SMS_SDK_APP_ID=<短信应用 SDKAppID>
TENCENT_SMS_SIGN=天津逑贝互联网医院
TENCENT_SMS_TEMPLATE_REGISTER_PHONE_ID=2695131
TENCENT_SMS_TEMPLATE_CHANGE_PHONE_ID=2695133
TENCENT_SMS_REGION=ap-guangzhou
TENCENT_SMS_CODE_TTL_SECONDS=300
TENCENT_SMS_SEND_INTERVAL_SECONDS=60
TENCENT_SMS_PHONE_DAILY_LIMIT=2
TENCENT_SMS_USER_HOURLY_LIMIT=5
TENCENT_SMS_IP_HOURLY_LIMIT=30
```

保存后：

```bash
chmod 600 .env
cd /opt/qiubei-health
git pull --ff-only
cd backend
dc up -d --build --wait --wait-timeout 120 api
dc exec -T api python -m scripts.tencent_sms_preflight
dc exec -T api python -m scripts.production_preflight
curl -ffS https://api.qb-medical.cn/health
```

短信预检应全部为 `OK`，并显示 `SKIP 未请求真实发送`。生产总预检中的“短信”应由
`WARN` 变为 `PASS`。

## 4. 模板生效后的真机验收

先确认腾讯云 4 个模板中至少 `2695131`、`2695133` 已显示“已生效”，再使用内部测试手机号：

```bash
cd /opt/qiubei-health/backend

dc exec -T api python -m scripts.tencent_sms_preflight \
  --live --phone <内部测试手机号> --purpose register_phone

sleep 65  # 至少间隔 60 秒；同一手机号当天只再测一次

dc exec -T api python -m scripts.tencent_sms_preflight \
  --live --phone <内部测试手机号> --purpose change_phone
```

逐项核对：

1. 两条短信签名均显示“天津逑贝互联网医院”。
2. 注册短信含 6 位验证码和“5 分钟”；修改手机号短信含 6 位验证码和模板固定的 5 分钟。
3. 60 秒内重复发送被本系统以 HTTP 429 拒绝。
4. 当天第 3 次向同一手机号发送被本系统拒绝，不继续消耗腾讯云请求。
5. 正确验证码仅成功一次，错误或超过 5 分钟的验证码失败。
6. 腾讯云调用记录中送达状态正常；系统日志中没有手机号和验证码明文。

最后用微信开发者工具重新上传患者端版本并真机走一遍“新增就诊人”和“修改手机号”。
医生端当前没有短信验证码业务，不需要为了凑验收而接入；它继续使用微信授权手机号登录。

## 5. 未完成判定

以下 4 项全部完成后，短信事项才可打勾关闭：

- [x] 模板 `2695131`、`2695133` 状态变为“已生效”（2026-07-26）
- [ ] 生产 `.env` 配置完成，短信预检和生产总预检均通过
- [ ] 两种用途各完成一次真机收码，内容和腾讯云送达记录一致
- [ ] 新患者端版本上传并完成新增/修改手机号端到端验证

## 6. 腾讯云官方参考

- [SendSms API（2021-01-11）](https://cloud.tencent.com/document/api/382/55981)
- [正文模板审核与状态说明](https://cloud.tencent.com/document/product/382/37795)
- [短信发送频率限制](https://cloud.tencent.com/document/product/382/37809)
- [验证码短信安全防护建议](https://cloud.tencent.com/document/faq/382/13303)
