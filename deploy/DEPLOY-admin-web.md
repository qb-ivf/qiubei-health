# 运营后台 admin-web 部署手册（与后端同机，静态站点 + 同源 /api 反代）

部署到 `https://admin.qb-medical.cn`，与后端 `api.qb-medical.cn` 共用同一台 Ubuntu 服务器、同一套 Nginx。

- admin-web 用相对路径 `baseURL: '/api/v1'` → 由本站 Nginx 把 `/api` 反代到后端 `127.0.0.1:8000`，**浏览器同源，无需 CORS**。
- 前端是 Vite 构建的纯静态文件，系统 Nginx 直接托管，不另起容器。

> 🔴 **安全前提**：后端 admin 登录当前为 mock（任意账号可登入，见 pending P0 #26）。**公网暴露前必须加 Basic Auth 门禁**（第 4 步），并建议加 IP 白名单。真实 RBAC 上线后再撤门禁。

---

## 第 0 步：阿里云控制台

1. **域名解析**：云解析 → `qb-medical.cn` → 加记录：主机记录 `admin`，类型 `A`，值 = 服务器公网 IP。
2. 安全组 80/443 已放行（与 api 同机，无需重复）。

---

## 第 1 步：构建静态文件（用临时 Node 容器，免装 Node）

```bash
cd /opt/qiubei-health
git pull                       # 确保拿到最新代码
cd admin-web
docker run --rm -v "$PWD":/app -w /app node:20-alpine sh -c \
  "npm install --registry=https://registry.npmmirror.com && npm run build"
ls dist                        # 应看到 index.html 和 assets/
```

## 第 2 步：发布到 Nginx 站点目录

```bash
mkdir -p /var/www/admin-web
rm -rf /var/www/admin-web/*
cp -r dist/* /var/www/admin-web/
```

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

## 第 6 步：验证

1. 浏览器开 `https://admin.qb-medical.cn` → 先弹 **Basic Auth 门禁**（输第 4 步账号）→ 进入运营后台登录页。
2. 登录页输入任意账号密码（当前 mock）→ 进入后台。
3. 打开「资质终审 / 药品字典 / 财务提现 / 监管面板」，确认能拉到后端数据（说明 `/api` 反代通）。

---

## 更新流程（以后改了 admin-web 代码）

```bash
cd /opt/qiubei-health && git pull
cd admin-web
docker run --rm -v "$PWD":/app -w /app node:20-alpine sh -c \
  "npm install --registry=https://registry.npmmirror.com && npm run build"
rm -rf /var/www/admin-web/* && cp -r dist/* /var/www/admin-web/
# 静态文件无需重载 Nginx；强刷浏览器即可
```

---

## 待办（撤门禁的前置）

- **真实 admin RBAC**（pending P0 #26）：管理员/药师/财务账号表 + 密码校验 + 角色权限。
  完成后即可去掉第 4 步的 Basic Auth，改由应用自身鉴权。
