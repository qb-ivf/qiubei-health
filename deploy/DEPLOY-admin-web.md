# 运营后台 admin-web 部署手册（与后端同机，静态站点 + 同源 /api 反代）

部署到 `https://admin.qb-medical.cn`，与后端 `api.qb-medical.cn` 共用同一台 Ubuntu 服务器、同一套 Nginx。

- admin-web 用相对路径 `baseURL: '/api/v1'` → 由本站 Nginx 把 `/api` 反代到后端 `127.0.0.1:8000`，**浏览器同源，无需 CORS**。
- 前端是 Vite 构建的纯静态文件，系统 Nginx 直接托管，不另起容器。

> 🔒 **登录鉴权**：后端已实现真实 RBAC（staff 账号 + bcrypt 密码 + 角色），账号用脚本创建（见第 7 步）。
> Nginx Basic Auth 门禁（第 4 步）可作为纵深防御保留，或在确认账号登录正常后撤除。

---

## 第 0 步：阿里云控制台

1. **域名解析**：云解析 → `qb-medical.cn` → 加记录：主机记录 `admin`，类型 `A`，值 = 服务器公网 IP。
2. 安全组 80/443 已放行（与 api 同机，无需重复）。

---

## 第 1 步：在【本地】构建静态文件（**不要在生产服务器构建**）

> ⚠️ 生产服务器还跑着 MySQL/Redis/支付后端，Vite 构建吃内存（峰值近 1G），在小机器上构建可能 OOM 卡死、连累线上服务。**务必在本地构建，只把产物传上去。**

本地 Windows（PowerShell），用临时 Node 容器构建（免装 Node）：
```powershell
cd c:\github\qiubei-health\admin-web
docker run --rm -v "${PWD}:/app" -v /app/node_modules -w /app node:20-alpine sh -c "npm install --registry=https://registry.npmmirror.com && npm run build"
# 完成后本地生成 dist\
```
> ⚠️ 必须带 `-v /app/node_modules`（匿名卷，让依赖装在容器内）。否则 Windows 下 Docker 绑定挂载会对 node_modules 报 `ENOTDIR: mkdir '/app/node_modules'`。

## 第 2 步：把 dist 传到服务器并就位

```powershell
# 本地：传到 /tmp（避免 PowerShell 通配符问题）
scp -r dist root@<ECS公网IP>:/tmp/admin-dist
```
```bash
# 服务器：移到 Nginx 站点目录
rm -rf /var/www/admin-web && mkdir -p /var/www && mv /tmp/admin-dist /var/www/admin-web
ls /var/www/admin-web          # 应看到 index.html 和 assets/
```

> 备选（不推荐）：若一定要在服务器构建，先加 swap 并用 `tmux`/`screen` 防 SSH 断线杀进程：
> `fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile`，
> 然后在 `tmux` 里执行构建。

## 第 3 步：申请并上传 SSL 证书（阿里云免费证书）

与 api 同流程：SSL 证书 → 免费证书 → 绑定 `admin.qb-medical.cn` → DNS 验证 → 下载 Nginx 格式：
```bash
ssh root@<IP> "mkdir -p /etc/nginx/ssl"
scp admin_xxx.pem root@<IP>:/etc/nginx/ssl/admin.qb-medical.cn.pem
scp admin_xxx.key root@<IP>:/etc/nginx/ssl/admin.qb-medical.cn.key
```

## 第 4 步：设置访问门禁（**必做**）

```bash
# 装 htpasswd 工具
apt -y install apache2-utils
# 创建门禁账号（按提示输入密码，记牢；换 yunying 为你想要的用户名）
htpasswd -c /etc/nginx/.htpasswd_admin yunying
# 如需多个账号，去掉 -c 再加：htpasswd /etc/nginx/.htpasswd_admin pharmacist
```
（可选）只放行办公网段：编辑配置里 `allow <你的办公出口IP>; deny all;` 取消注释。

## 第 5 步：放置 Nginx 配置并重载

```bash
# 本地执行，上传仓库里的配置：
#   scp deploy/nginx/admin.qb-medical.cn.conf root@<IP>:/etc/nginx/conf.d/
nginx -t && systemctl reload nginx
```

## 第 7 步：创建运营后台账号（真实 RBAC）

在服务器后端目录，用脚本创建账号（密码在服务器输入，不经聊天/不入库）：
```bash
cd /opt/qiubei-health/backend
# role：admin（全权）/ pharmacist（药师审方）/ finance（财务）
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api \
  python -m scripts.create_admin yunying '设一个强密码' admin
# 按需再建药师/财务账号
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec api \
  python -m scripts.create_admin yaoshi '强密码2' pharmacist
```
> 首次运行会自动建 `staff` 表。重复运行同一用户名 = 重置该账号密码。
> ⚠️ 后端代码/依赖更新过（新增 bcrypt），重新部署时重建镜像：
> `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build`

## 第 6 步：验证

1. 浏览器开 `https://admin.qb-medical.cn` → 先弹 **Basic Auth 门禁**（输第 4 步账号）→ 进入运营后台登录页。
2. 登录页输入**第 7 步创建的账号密码** → 进入后台（错误密码会被拒绝）。
3. 打开「资质终审 / 药品字典 / 财务提现 / 监管面板」，确认能拉到后端数据（说明 `/api` 反代通）。

> 账号登录验证正常后，若不需要双重门禁，可去掉第 4/5 步 Nginx 配置里的 `auth_basic` 两行再 `reload`。

---

## 更新流程（以后改了 admin-web 代码）

同样【本地构建、scp 上传】，不在服务器构建：
```powershell
# 本地
cd c:\github\qiubei-health\admin-web
docker run --rm -v "${PWD}:/app" -v /app/node_modules -w /app node:20-alpine sh -c "npm install --registry=https://registry.npmmirror.com && npm run build"
scp -r dist root@<ECS公网IP>:/tmp/admin-dist
```
```bash
# 服务器
rm -rf /var/www/admin-web && mkdir -p /var/www && mv /tmp/admin-dist /var/www/admin-web
# 静态文件无需重载 Nginx；强刷浏览器即可
```

---

## 待办（撤门禁的前置）

- **真实 admin RBAC**（pending P0 #26）：管理员/药师/财务账号表 + 密码校验 + 角色权限。
  完成后即可去掉第 4 步的 Basic Auth，改由应用自身鉴权。
