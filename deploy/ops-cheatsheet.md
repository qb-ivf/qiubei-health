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
```

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

admin-web 是纯静态站点：本机构建出 `dist/`，scp 到服务器 `/var/www/admin-web`，Nginx 直接托管
（站点配置 `deploy/nginx/admin.qb-medical.cn.conf`，`/api/` 反代到 8000 后端）。

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

### 8.2 上传 + 落位（服务器）
```powershell
# ⚠️ 必须先删临时目录，否则 scp -r 会套娃成 /tmp/admin-dist/dist
ssh root@<服务器IP> "rm -rf /tmp/admin-dist"     # 确认无 Permission denied 才算删成功
scp -r dist root@<服务器IP>:/tmp/admin-dist
```
```bash
# 服务器：整目录替换
rm -rf /var/www/admin-web && mv /tmp/admin-dist /var/www/admin-web
ls /var/www/admin-web/index.html        # 必须在顶层（不是 .../admin-web/dist/index.html）
ls /var/www/admin-web/assets/ | wc -l    # 资源齐全（构建时会打印总数）
# 一般无需 reload nginx；改了 nginx 配置才需要：nginx -t && systemctl reload nginx
```
改完浏览器 **Ctrl+F5** 强刷（避免缓存旧 index 去拿对不上的分片）。

### 8.3 常见报错对照（都在 Nginx/前端层，不是后端）
| 现象 | 原因 | 处理 |
|---|---|---|
| 整页 `500 Internal Server Error`（nginx 字样） | `/var/www/admin-web/index.html` 不存在，`try_files` 兜底文件缺失 | 多半是套娃，`index.html` 跑到 `dist/` 里了；按 8.2 重新落位 |
| `Failed to fetch dynamically imported module .../assets/Xxx.js` | 分片缺失，被 `try_files` 兜底成 index.html | dist 上传不完整，按 8.2 干净重传 |
| `auth_basic_user_file ... failed` | `/etc/nginx/.htpasswd_admin` 丢了 | 重建 htpasswd |

---

## 安全/注意
- `.env`、`backend/secrets/` 含密钥，**勿外泄、勿入库**（已 gitignore）。
- 直接改库要谨慎：状态字段尽量走业务接口流转，避免破坏订单状态机。
- 生产改完任何 `.env` 都要 `dc restart api` 才生效。
