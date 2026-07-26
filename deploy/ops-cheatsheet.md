# 后端运维速查表（生产服务器常用命令）

服务器后端目录：`/opt/qiubei-health/backend`。生产用 prod 叠加文件启动。
所有命令默认在该目录执行：`cd /opt/qiubei-health/backend`。

> 💡 为少打字，可设别名：
> ```bash
> alias dc='docker compose -f docker-compose.yml -f docker-compose.prod.yml'
> ```
> 下面用 `dc` 代指 `docker compose -f docker-compose.yml -f docker-compose.prod.yml`。

---

## 1. 部署 / 更新代码

```bash
cd /opt/qiubei-health/backend
git pull                         # 拉最新代码
dc restart api                   # 重启加载新代码（代码是卷挂载，通常无需重建镜像）

# 仅当 requirements.txt 变了才重建镜像：
dc up -d --build

# 若本次提交含模型变更（新表/新列），重启前先跑迁移（幂等，重复执行安全）：
dc exec api python -m scripts.init_db      # 建缺失的新表
dc exec api python -m scripts.migrate      # 给已有表补列
```

### 1.1 ⚠️ 本次版本（天津监管改造，2026-07）部署清单

本次改了依赖（gmssl/openpyxl）、加了 3 张新表（evaluations/medical_disputes/icd10_codes）、
32 条补列、需导入 ICD-10 字典。**按顺序执行，缺一不可**：

```bash
cd /opt/qiubei-health/backend
git pull

# ① requirements 变了 → 必须重建镜像（会自动重启）
dc up -d --build

# ② 建新表（生产 DEBUG=false 不自动建表）
dc exec api python -m scripts.init_db

# ③ 补列（orders 时间戳/复诊字段、prescriptions ICD、doctors/staff/patients/drugs 监管字段、gov_reports 扩列）
dc exec api python -m scripts.migrate

# ④ 导入 ICD-10 编码库（读仓库内 docs/specs/tianjin/*.xlsx，西医 35862 + 中医 1890 条，约半分钟）
dc exec api python -m scripts.import_icd10

# ⑤ 验证
curl http://127.0.0.1:8000/health
dc logs --tail=30 api                        # 无报错、能看到后台任务启动
dc exec mysql mysql -uqiubei -pqiubei qiubei -e "SELECT count(*) FROM icd10_codes;"   # ≈37752
dc exec mysql mysql -uqiubei -pqiubei qiubei -e "SHOW COLUMNS FROM orders LIKE 'paid_at';"  # 存在
dc exec mysql mysql -uqiubei -pqiubei qiubei -e "SHOW TABLES LIKE 'medical_disputes';"      # 存在
```

然后按第 8 节重新构建部署 admin-web（本次有 5 个页面改动/新增）。

**小程序**：后端新接口对旧版小程序完全向后兼容（旧版不传复诊声明/ICD 也能正常下单开方），
可先上后端；两端小程序在微信开发者工具上传新版本、提审，审核期间线上旧版不受影响。

**`.env` 无需在普通部署步骤中开启监管上报**：`TJ_REPORT_ENABLED=false` 时生产队列保持 pending；
正式切换必须单独按第 9 节完成预检和目录初始化。

**回滚**：`git log --oneline` 找上一版本 → `git checkout <hash>` → `dc up -d --build`。
迁移只加表/加列不删改，旧代码跑在新表结构上无影响，**无需回滚数据库**。

### 1.2 生产安全总预检与数据库/Redis 端口收敛

每次正式发布后执行只读预检。它不写数据库、不访问外网，也不会输出任何密钥；`FAIL` 必须处理，
`WARN` 是尚未开通或仍需人工验收的能力：

```bash
dc exec -T api python -m scripts.production_preflight
echo $?   # 0=无 FAIL；1=仍有阻断项
```

当前 Compose 已把宿主机 MySQL `3306`、Redis `6379` 绑定到 `127.0.0.1`，避免直接暴露到公网。
这一变更涉及容器端口映射，首次部署本版本不能只执行 `dc restart api`，必须：

```bash
git pull --ff-only
dc up -d
dc ps
ss -lntp | grep -E ':(3306|6379)\b'
# 正确结果只能看到 127.0.0.1:3306 和 127.0.0.1:6379，不应是 0.0.0.0 或 [::]
```

`MYSQL_ROOT_PASSWORD/MYSQL_USER/MYSQL_PASSWORD/MYSQL_DATABASE` 现可由服务器 `.env` 注入。
但已有 MySQL 数据卷只修改 `.env` **不会自动修改库内账号密码**，反而会令 API 无法连接；
密码轮换必须在维护窗口内先执行数据库 `ALTER USER`，再同步 `.env` 后 `dc up -d`。
本次仅收敛监听地址，不自动改现有数据库口令。

## 2. 服务状态 / 日志 / 健康

```bash
dc ps                            # 容器状态
dc logs --tail=50 api            # 看最近日志
dc logs -f api                   # 实时跟踪日志（Ctrl+C 退出）
curl http://127.0.0.1:8000/health   # 健康检查，应 {"status":"ok",...}
dc restart api                   # 重启后端
dc down                          # 停全部（谨慎：会停 MySQL/Redis）
dc up -d                         # 起全部
```

## 3. 进数据库 / 常用查询

进入 MySQL（库 `qiubei`，账号/密码 `qiubei`/`qiubei`）：
```bash
dc exec mysql mysql -uqiubei -pqiubei qiubei
```
单条查询直接 `-e`（会有一行 password 警告，忽略即可）：
```bash
dc exec mysql mysql -uqiubei -pqiubei qiubei -e "SELECT ...;"
```

常用：
```bash
# 医生列表 + 挂号费(分) + 审核状态
dc exec mysql mysql -uqiubei -pqiubei qiubei \
  -e "SELECT id,name,register_fee_fen,audit_status FROM doctors;"

# 最近订单（status 见下方对照）
dc exec mysql mysql -uqiubei -pqiubei qiubei \
  -e "SELECT id,order_no,status,register_fee_fen,drug_fee_fen FROM orders ORDER BY id DESC LIMIT 10;"

# 运营后台账号
dc exec mysql mysql -uqiubei -pqiubei qiubei -e "SELECT id,username,role,active FROM staff;"

# 患者/用户数量
dc exec mysql mysql -uqiubei -pqiubei qiubei \
  -e "SELECT count(*) AS patients FROM patients; SELECT count(*) AS users FROM users;"
```

### 订单 status 对照
| 值 | 含义 |
|---|---|
| 0 | 待支付 PENDING |
| 1 | 候诊中 WAITING |
| 2 | 问诊中 CONSULTING |
| 3 | 待药师审方 AUDITING |
| 4 | 审方驳回 REJECTED |
| 5 | 已开方 PRESCRIBED |
| 6 | 已完成 FINISHED |
| 7 | 已退款 REFUNDED |
| 9 | 已取消 CANCELLED |

## 4. 准备「1 分钱挂号费」测试号源（真实支付联调）

挂号费单位是**分**：1 分 = `register_fee_fen=1`（= ¥0.01，微信支付最低 1 分）。

```bash
# 先看医生，挑一个 id
dc exec mysql mysql -uqiubei -pqiubei qiubei -e "SELECT id,name,register_fee_fen FROM doctors;"

# 把某医生(如 id=1)挂号费改成 1 分
dc exec mysql mysql -uqiubei -pqiubei qiubei \
  -e "UPDATE doctors SET register_fee_fen=1 WHERE id=1; SELECT id,name,register_fee_fen FROM doctors WHERE id=1;"
```
测完**务必改回正常价**（如 ¥40 = 4000 分）：
```bash
dc exec mysql mysql -uqiubei -pqiubei qiubei -e "UPDATE doctors SET register_fee_fen=4000 WHERE id=1;"
```
> ⚠️ 这是真实环境：改成 1 分期间，真实患者挂这个医生也只付 1 分。测试窗口尽量短，测完立刻改回。
> 该医生还需有可约号源（`slots` 表）且 `audit_status='approved'`、`name` 非空，患者端才看得到。

## 4.5 给医生插号源（患者才能约号）

医生通过审核后会出现在患者端列表，但**没有可约时段**就挂不上号。号源扣减以 Redis 为准，
所以**必须用脚本插**（脚本会同步写 Redis），纯 SQL 插 `slots` 会被判「约满」。

```bash
# 给医生 <doctor_id> 从今天起 N 天、每天 5 个时段，每个时段 quota 个号
# 用法：python -m scripts.add_slots <doctor_id> [天数=3] [每时段配额=5]
dc exec api python -m scripts.add_slots 4 3 5

# 先查医生 id：
dc exec mysql mysql -uqiubei -pqiubei qiubei -e "SELECT id,name,dept,audit_status FROM doctors;"
# 查某医生的号源：
dc exec mysql mysql -uqiubei -pqiubei qiubei -e "SELECT id,day,start_time,remaining FROM slots WHERE doctor_id=4 ORDER BY day,start_time;"
```
> 可重复运行（同日同时段不重复插）。时段在 `scripts/add_slots.py` 的 `TIMES` 里改。

## 4.6 清理示例/演示医生（生产首次部署遗留）

最初用 `DEBUG=true` 建表时 seed 写入过示例医生（user_id 1001/1002/1003）。生产应删除，
只保留真实注册医生：
```bash
dc exec mysql mysql -uqiubei -pqiubei qiubei -e "DELETE FROM slots WHERE doctor_id IN (SELECT id FROM doctors WHERE user_id IN (1001,1002,1003)); DELETE FROM doctors WHERE user_id IN (1001,1002,1003);"
dc exec mysql mysql -uqiubei -pqiubei qiubei -e "SELECT id,name,dept,audit_status FROM doctors;"
```

## 5. 运营后台账号管理

```bash
# 新建/重置账号（role: admin / pharmacist / finance）
dc exec api python -m scripts.create_admin <用户名> '<强密码>' admin
# 重复同一用户名 = 重置其密码
```

## 6. Redis（号源锁 / 排队队列，一般不用手动动）

```bash
dc exec redis redis-cli
# 某时段剩余号源
dc exec redis redis-cli GET slot:remaining:<slot_id>
# 某医生排队队列
dc exec redis redis-cli LRANGE room:queue:<doctor_id> 0 -1
```

## 7. 切换医生白名单模式（上线前）

```bash
# 生产：医生须走 admin 资质终审（默认应为 false）
# 编辑 .env：DOCTOR_AUTO_APPROVE=false  然后：
dc restart api
```

## 8. 运营后台 admin-web 部署 / 更新（前端静态站）

admin-web 是纯静态站点：本机构建 `dist/` 并上传压缩包，服务器校验内容和权限后再切换到
`/var/www/admin-web`，由 Nginx 直接托管（站点配置 `deploy/nginx/admin.qb-medical.cn.conf`，
`/api/` 反代到 8000 后端）。

### 8.1 构建 dist
本机装了 Node 就直接：
```powershell
cd admin-web
npm run build            # 产物在 admin-web/dist
```
本机没装 Node、但有 Docker 时（零本地安装，推荐）：
```powershell
cd admin-web
# node_modules 用容器内独立卷，不碰宿主机；dist 会落到宿主机 admin-web/dist
docker run --rm -v "${PWD}:/app" -v /app/node_modules -w /app node:20-alpine `
  sh -c "npm install && npm run build"
```

### 8.2 打包并上传（本机 PowerShell）

不要直接 `scp -r dist` 后 `rm -rf /var/www/admin-web`：目录套娃、上传中断或权限继承异常会造成
整站 403/500，且旧版本已被删除时无法立即回退。改为上传单个压缩包：

```powershell
# 当前目录为 admin-web；先确认入口和资源目录都存在
Test-Path .\dist\index.html
Test-Path .\dist\assets

tar -czf admin-web-dist.tar.gz -C dist .
scp .\admin-web-dist.tar.gz root@120.27.157.116:/tmp/admin-web-dist.tar.gz

# 上传成功后清理本地临时包，禁止提交 Git
Remove-Item .\admin-web-dist.tar.gz
```

### 8.3 校验权限并切换（生产服务器）

先解压到带时间戳的新目录，统一修复为“目录 0755、文件 0644”，确认 Nginx 用户可读后再切换。
旧站点按时间戳保留，不使用 `rm -rf`：

```bash
set -e

stamp="$(date +%Y%m%d%H%M%S)"
archive="/tmp/admin-web-dist.tar.gz"
release="/var/www/admin-web-release-${stamp}"
current="/var/www/admin-web"
backup="/var/www/admin-web-backup-${stamp}"

test -f "$archive"
install -d -m 0755 "$release"
tar -xzf "$archive" -C "$release"

# 防止空包、dist 套娃或 Windows 压缩包权限导致 Nginx 403
test -f "$release/index.html"
test -d "$release/assets"
find "$release" -type d -exec chmod 0755 {} +
find "$release" -type f -exec chmod 0644 {} +
chown -R root:root "$release"
runuser -u www-data -- test -r "$release/index.html"
runuser -u www-data -- test -x "$release/assets"

# Nginx 配置不变也先做语法检查；失败时不切站
nginx -t

# 保留旧版后切换；若新目录落位失败，立即恢复旧版
moved_old=0
if [ -e "$current" ]; then
  mv "$current" "$backup"
  moved_old=1
fi
if ! mv "$release" "$current"; then
  [ "$moved_old" -eq 1 ] && mv "$backup" "$current"
  exit 1
fi

test -r "$current/index.html"
namei -l "$current/index.html"
ls "$current/assets/" | wc -l
rm -f "$archive"

# 仅替换静态文件一般无需 reload；若同时改过 Nginx 配置才执行：
# systemctl reload nginx
```

改完浏览器 **Ctrl+F5** 强刷（避免缓存旧 index 去拿对不上的分片）。

回滚时先从 `ls -dt /var/www/admin-web-backup-*` 中人工确认目标版本，再执行：

```bash
backup="/var/www/admin-web-backup-YYYYMMDDHHMMSS"  # 替换成已确认的实际目录
test -f "$backup/index.html"
failed="/var/www/admin-web-failed-$(date +%Y%m%d%H%M%S)"
mv /var/www/admin-web "$failed"
mv "$backup" /var/www/admin-web
```

### 8.4 常见报错对照

| 现象 | 原因 | 处理 |
|---|---|---|
| 整页 `403 Forbidden`（nginx 字样） | 新目录或文件不可被 Nginx 用户读取/穿越 | 执行 `find /var/www/admin-web -type d -exec chmod 0755 {} +`、`find /var/www/admin-web -type f -exec chmod 0644 {} +`，再用 `namei -l /var/www/admin-web/index.html` 检查父目录权限 |
| 整页 `500 Internal Server Error`（nginx 字样） | `/var/www/admin-web/index.html` 不存在，`try_files` 兜底文件缺失 | 多半是套娃，`index.html` 跑到 `dist/` 里了；按 8.3 重新校验并切换 |
| `Failed to fetch dynamically imported module .../assets/Xxx.js` | 分片缺失，被 `try_files` 兜底成 index.html | dist 上传不完整，按 8.2 重新打包上传，再按 8.3 切换 |
| `auth_basic_user_file ... failed` | `/etc/nginx/.htpasswd_admin` 丢了 | 重建 htpasswd |
| 新页面能打开，但顶部提示 `Not found` | 新前端已发布，后端仍是旧进程，新 API 路由尚未加载 | 服务器仓库执行 `git pull --ff-only`，进入 `backend` 后执行 `dc restart api`，再用 `/health` 和对应 API 验证 |

---

## 9. 天津监管上报运维（docs/tianjin_supervision_plan.md）

后端每日**北京时间 01:30** 自动采集前一日终态数据入 `gov_reports` 队列，后台 worker 每 15s 消费。
`TJ_REPORT_ENABLED=false` 时：`DEBUG=true` 的开发环境模拟成功；`DEBUG=false` 的生产环境会把任务保持为
`pending`，**不发送、也不会伪装成功吞掉队列**。

### 9.1 测试环境联调
编辑 `.env` 追加，然后 `dc restart api`：
```bash
TJ_REPORT_ENABLED=true
TJ_GATEWAY_URL=https://imssp.wsjk.tj.gov.cn/net-diag-service/test-openapi/api
TJ_APP_KEY=<appKey>
TJ_APP_SECRET=<appSecret，32位hex>
TJ_UNIT_ID=<监管平台机构ID>
ORGAN_ID=<统一组织机构代码>
ORGAN_NAME=<机构登记全称>
```
先跑连通性自检（黄金向量对拍 + 真实调用 1 条演示药品）。脚本自动读取 `.env` 的 TJ_* 配置，
**无需改代码、无需在宿主机 pip install**（容器镜像已含 gmssl/httpx）：
```bash
dc exec api python scripts/tj_ping.py
# 若报 ModuleNotFoundError: gmssl → 镜像未重建：dc up -d --build 后重试
```

`tj_smoke.py` 只允许测试网关；检测到正式网关会强制退出，避免合成患者/处方污染正式数据。

### 9.2 正式环境首次切换（按顺序）

1. 先写正式 URL/appKey/appSecret，但保持 `TJ_REPORT_ENABLED=false`；确认 `DEBUG=false`、
   `ENCRYPTION_KEY` 与非默认 `JWT_SECRET` 均已配置。
2. 只读预检（不写库、不请求平台），必须达到 **0 FAIL**：

```bash
dc exec api python scripts/tj_preflight.py
```

3. 预览并初始化全部真实在用药品目录任务（执行阶段只写本地队列，仍不请求平台）：

```bash
dc exec api python scripts/tj_bootstrap_drugs.py
dc exec api python scripts/tj_bootstrap_drugs.py --apply --confirm-unit 20250813151647906
```

4. 将 `.env` 的 `TJ_REPORT_ENABLED` 改为 `true`，执行 `dc restart api`。worker 会优先发送药品目录，
   再发送其他业务任务。先确认目录全部 success，次日再核验 01:30 批次和不良事件签到。

> `tj_ping.py` 在正式网关默认拒绝写演示药品；正常正式验密由上述真实目录首批完成。

### 9.3 查看上报队列状态
```bash
# 按接口/状态统计（success/pending/failed/dead）
dc exec mysql mysql -uqiubei -pqiubei qiubei \
  -e "SELECT method,status,count(*) FROM gov_reports GROUP BY method,status;"

# 不良事件每日签到是否正常（监管强制，每日一条，空数组也要发）
dc exec mysql mysql -uqiubei -pqiubei qiubei \
  -e "SELECT id,batch_date,status,msg_code,resp_msg FROM gov_reports WHERE biz_type='dispute_signin' ORDER BY id DESC LIMIT 5;"

# 死信（数据错误，需改数后在后台重报）
dc exec mysql mysql -uqiubei -pqiubei qiubei \
  -e "SELECT id,method,biz_id,last_error FROM gov_reports WHERE status='dead' ORDER BY id DESC LIMIT 10;"
```
日常操作优先走 **admin-web「监管上报面板」**：按接口统计、签到状态、失败任务看报文/一键重报、按日补采（漏采某天时用）。

### 9.4 注意
- 一个业务终态只上报一次（`(biz_type,biz_id)` 幂等）；重复补采同一天不会产生重复任务。
- `failed` 会按退避（5m→6h）自动重试；`dead` 不再自动重试，改完数据后在面板点"重新上报"。
- 首诊材料图片在 `backend/uploads/fd_*` 院内留存；平台已书面确认没有 `uploadFile`，本地路径不会外发。

## 10. 数据库与文件备份（生产必备）

MySQL 与 uploads 保留每日短周期备份；签后处方 PDF 使用独立密钥做 AES-256-GCM
流式加密归档，并在每次创建后立即回读校验。**归档密钥不得放进归档目录或备份包。**

### 10.1 MySQL 与 uploads

```bash
install -d -m 700 /opt/backups
crontab -e
```

```cron
30 2 * * * docker compose -f /opt/qiubei-health/backend/docker-compose.yml -f /opt/qiubei-health/backend/docker-compose.prod.yml exec -T mysql mysqldump -uqiubei -pqiubei --single-transaction qiubei | gzip > /opt/backups/qiubei-$(date +\%F).sql.gz && tar czf /opt/backups/uploads-$(date +\%F).tgz -C /opt/qiubei-health/backend uploads 2>/dev/null
40 2 * * * find /opt/backups -maxdepth 1 -type f \( -name 'qiubei-*.sql.gz' -o -name 'uploads-*.tgz' \) -mtime +14 -delete
```

上面的清理规则只处理数据库和 uploads，不得删除 `prescriptions/` 中需要长期保存的签后处方归档。
`.env` 含生产密钥，不可直接打入普通压缩包；应使用组织批准的密码库/KMS 做独立备份。

### 10.2 签后处方加密归档首次配置

先在服务器终端生成专用密钥。命令会在当前终端显示一次密钥，禁止截图、粘贴到聊天或写入 Git：

```bash
cd /opt/qiubei-health/backend
dc exec -T api python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

将结果写入受保护的 `backend/.env`：

```dotenv
FXQ_ARCHIVE_KEY=<刚生成的密钥>
```

把同一密钥另存到组织批准的密码库/KMS，且与备份文件分开。然后部署代码并执行：

```bash
install -d -m 700 /opt/backups/prescriptions
dc exec -T api python -m scripts.fxq_storage fix-permissions
dc exec -T api python -m scripts.fxq_storage check --write-test

dc run --rm --no-deps \
  -v /opt/backups/prescriptions:/backup:rw \
  api python -m scripts.fxq_storage backup /backup/prescriptions-first.qba

dc run --rm --no-deps \
  -v /opt/backups/prescriptions:/backup:ro \
  api python -m scripts.fxq_storage verify /backup/prescriptions-first.qba
```

命令只输出文件数量和总字节数，不输出处方内容、患者信息或密钥。归档拒绝覆盖已有文件。

### 10.3 空目录恢复演练

恢复工具不会写入生产持久卷，也不会覆盖目标目录；目标必须是已存在的空目录：

```bash
install -d -m 700 /opt/restore-tests/prescriptions-first
dc run --rm --no-deps \
  -v /opt/backups/prescriptions:/backup:ro \
  -v /opt/restore-tests/prescriptions-first:/restore:rw \
  api python -m scripts.fxq_storage restore-test /backup/prescriptions-first.qba /restore
```

成功后由授权人员抽查文件数量和 PDF 可读性，记录演练日期、归档文件名、数量和结果；
演练副本按院内敏感数据清理流程及时销毁。归档密钥错误、文件被篡改、清单摘要不一致时必须失败。

### 10.4 每日处方归档

首次备份和恢复演练通过后，再加入每日任务：

```cron
50 2 * * * cd /opt/qiubei-health/backend && docker compose -f docker-compose.yml -f docker-compose.prod.yml run --rm --no-deps -v /opt/backups/prescriptions:/backup:rw api python -m scripts.fxq_storage backup /backup/prescriptions-$(date +\%F-\%H\%M\%S).qba >> /var/log/qiubei-prescription-backup.log 2>&1
```

本地加密归档只解决单机误读和短期恢复，不等同于合规长期存证。仍须将 `.qba` 同步到异地
OSS/对象锁存储，设置与院方法务确认的保留期，并定期从异地副本做恢复演练；密钥丢失将无法恢复。

### 10.5 数据库恢复

```bash
ls -lh /opt/backups | tail -5
# 谨慎：先 dc stop api 停止写入，再恢复到经确认的目标库
gunzip < /opt/backups/qiubei-2026-07-02.sql.gz | dc exec -T mysql mysql -uqiubei -pqiubei qiubei
```

---

## 安全/注意
- `.env`、`backend/secrets/` 含密钥，**勿外泄、勿入库**（已 gitignore）。
- 直接改库要谨慎：状态字段尽量走业务接口流转，避免破坏订单状态机。
- 生产改完任何 `.env` 都要 `dc restart api` 才生效。
- `TJ_APP_SECRET` 同时是国密 SM4 密钥，泄露 = 可伪造本院监管上报，与支付密钥同级保管。
