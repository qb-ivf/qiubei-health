# 阿里云 Ubuntu 22.04 部署手册（后端 + 微信支付回调上线）

目标：把后端跑在 `https://api.qb-medical.cn`，让微信支付回调可达，切换到真实支付。

- 服务器：**新购** 阿里云 ECS / 轻量应用服务器，**Ubuntu 22.04 LTS**，2核4G 起，独占（**不要**与第三方 HIS `hisCloudProd` 混部）
- 域名：`qb-medical.cn`（已 ICP 备案，津ICP备2025029195号）
- 子域名：`api.qb-medical.cn`（主域名已备案，**子域名无需单独备案**，加解析即可）

> 备案是「主体 + 域名」级别，**不绑定具体机器**。新机器在同一阿里云账号下，解析指过去即可，无需重新备案。

---

## 第 0 步：阿里云控制台（网页操作）

1. **安全组**：放行入方向 **22**（SSH）、**80**、**443**（TCP）。**不要**对公网放行 8000（仅本机 Nginx 访问）。
2. **域名解析**：云解析 DNS → `qb-medical.cn` → 添加记录
   - 主机记录 `api`，类型 `A`，记录值 = 新 ECS 公网 IP。
3. 解析生效要几分钟，先点了在后台跑着。

---

## 第 1 步：连服务器 + 系统更新

```bash
ssh root@<ECS公网IP>      # 阿里云 Ubuntu 默认 root；若是 ubuntu 用户则 sudo -i
apt update && apt -y upgrade
timedatectl set-timezone Asia/Shanghai   # 时间要准，签名/验签依赖
```

---

## 第 2 步：安装 Docker + Compose（阿里云镜像加速）

```bash
apt -y install ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://mirrors.aliyun.com/docker-ce/linux/ubuntu/gpg \
  | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://mirrors.aliyun.com/docker-ce/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" \
  > /etc/apt/sources.list.d/docker.list
apt update
apt -y install docker-ce docker-ce-cli containerd.io docker-compose-plugin
systemctl enable --now docker
docker compose version    # 验证
```

### 2.1 配置镜像加速器（**必做**，否则拉镜像超时）

国内服务器直连 Docker Hub 会 `i/o timeout`，拉不下 mysql/redis 镜像。需配阿里云镜像加速器：

- 阿里云控制台 → **容器镜像服务 ACR** → 镜像工具 → **镜像加速器** → 复制你的专属地址（形如 `https://xxxx.mirror.aliyuncs.com`）

```bash
mkdir -p /etc/docker
cat > /etc/docker/daemon.json <<'EOF'
{
  "registry-mirrors": [
    "https://<你的ID>.mirror.aliyuncs.com",
    "https://docker.m.daocloud.io",
    "https://dockerproxy.com"
  ]
}
EOF
systemctl daemon-reload && systemctl restart docker
docker info | grep -A3 "Registry Mirrors"   # 确认生效
```
> 把第一行 `<你的ID>` 换成你的专属地址；后两个是公共备用，多配兜底。

---

## 第 3 步：拉代码 + 上传机密 + 启动后端

```bash
apt -y install git
mkdir -p /opt && cd /opt
git clone <你的仓库地址> qiubei-health
cd qiubei-health/backend
```

机密文件**不在 git 里**，从你本地 Windows（Git Bash）上传：
```bash
# —— 在本地 c:\github\qiubei-health 目录执行 ——
scp backend/.env root@<ECS公网IP>:/opt/qiubei-health/backend/.env
scp backend/secrets/apiclient_key.pem root@<ECS公网IP>:/opt/qiubei-health/backend/secrets/apiclient_key.pem
```

回到服务器，限权并启动：
```bash
cd /opt/qiubei-health/backend
chmod 600 secrets/apiclient_key.pem
docker compose up -d        # 起 mysql + redis + api
docker compose logs -f api  # 看启动日志，Ctrl+C 退出
curl http://127.0.0.1:8000/health   # 应返回 {"status":"ok",...}
```

> 初次部署 `.env` 保持 `DEBUG=true`：后端靠它自动建表（Alembic 迁移尚未接入，见 pending #21）。
> 生产强化（正式对外前）：换 `JWT_SECRET`、设 `ENCRYPTION_KEY`、收敛 CORS（pending #8/#9/#23）。

---

## 第 4 步：申请并上传 SSL 证书（阿里云免费证书）

1. 阿里云控制台 → **数字证书管理服务（SSL 证书）→ 免费证书 → 创建证书 → 申请**
2. 绑定域名 `api.qb-medical.cn`，用 **DNS 自动验证**，等签发（几分钟）。
3. 签发后 **下载 → 选 Nginx 格式**，得到 `xxx.pem` 和 `xxx.key`。
4. 上传到服务器（本地执行）：
```bash
ssh root@<ECS公网IP> "mkdir -p /etc/nginx/ssl"
scp xxx.pem root@<ECS公网IP>:/etc/nginx/ssl/api.qb-medical.cn.pem
scp xxx.key root@<ECS公网IP>:/etc/nginx/ssl/api.qb-medical.cn.key
```

> 免费证书有效期 1 年，到期前需重新申请并替换。

---

## 第 5 步：安装并配置 Nginx

```bash
apt -y install nginx
# 上传本仓库的 Nginx 配置（本地执行）：
#   scp deploy/nginx/api.qb-medical.cn.conf root@<IP>:/etc/nginx/conf.d/
# Ubuntu 的 nginx 默认会加载 /etc/nginx/conf.d/*.conf；如未加载，确认 nginx.conf 的 http 块含
#   include /etc/nginx/conf.d/*.conf;
systemctl enable nginx
nginx -t && systemctl restart nginx

# 防火墙（Ubuntu 用 ufw；若启用了 ufw 则放行，未启用可跳过——安全组已控）
ufw allow OpenSSH
ufw allow 'Nginx Full'    # 放行 80 + 443
# ufw enable              # 仅在你确认 22 已放行后再开，避免把自己锁外面
```

浏览器访问 `https://api.qb-medical.cn/health` 应返回 `{"status":"ok"}` 且证书有效（小绿锁）。

---

## 第 6 步：切换到真实支付

编辑 `/opt/qiubei-health/backend/.env`：
```
WX_PAY_NOTIFY_URL=https://api.qb-medical.cn/api/v1/orders/pay/callback
```
```bash
cd /opt/qiubei-health/backend && docker compose restart api
```
此时 `pay_service.is_enabled()` 自动变 True → 走真实微信支付 V3。

---

## 第 7 步：微信小程序后台配置

小程序后台（mp.weixin.qq.com）→ 开发管理 → 开发设置 → **服务器域名 → request 合法域名**：
添加 `https://api.qb-medical.cn`（必须是已备案的 HTTPS 域名）。

---

## 第 8 步：联调验证

1. `curl https://api.qb-medical.cn/health` → ok
2. 患者端真实登录（真 openid），挂一个 **1 分钱** 测试号，走 `wx.requestPayment` 真实支付。
3. 服务器看回调日志：`docker compose logs -f api`，订单状态 PENDING(0) → WAITING(1) 即闭环成功。

---

## 常见坑

| 现象 | 排查 |
| :- | :- |
| `https://api.qb-medical.cn` 打不开 | 安全组 80/443 是否放行；DNS 是否生效（`ping api.qb-medical.cn`）；`nginx -t` |
| 回调验签失败 | 服务器时间是否准（`timedatectl`，偏差大签名会挂）；APIv3 密钥/证书序列号是否与商户平台一致；Nginx 是否改写了 body（本仓库配置已避免） |
| 下单报 `缺少支付者 openid` | 患者用真实微信登录（`WX_PATIENT_SECRET` 已配），不是 dev mock 账号 |
| ufw 开启后 SSH 断连 | 开 ufw 前务必先 `ufw allow OpenSSH`；被锁可在阿里云控制台 VNC 登录解 |

---

## 采购建议（给你买服务器时参考）

- **机型**：阿里云 ECS 通用型 或 轻量应用服务器，**2核4G 起**（初期够用，后续可升配）
- **系统镜像**：**Ubuntu 22.04 LTS 64 位**
- **地域**：与备案/业务一致的大陆地域（如华北-北京/华东）
- **磁盘**：系统盘 40G+ SSD；数据量大可挂数据盘给 MySQL
- **网络**：固定公网 IP + 按量/固定带宽 3M 起
- **务必独立**：这台只跑你的新后端，**不要**和第三方 HIS 共用
