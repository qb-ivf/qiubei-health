# VS Code + AI 智能体开发后端 SaaS 系统实操指南

本指南旨在指导研发团队如何利用 **VS Code** 作为核心代码编辑器，配合 **Gemini 3.1 Pro / Claude Code** 智能体，基于 **Python FastAPI** 框架全自动、高质高效地构建互联网医院 SaaS 后端四大子系统。

> 🧭 **工程位置（与小程序同仓）：** 后端位于本仓库 `backend/`，PC 运营管理端（Vue3 + Element Plus）位于 `admin-web/`，与 `miniprogram-patient/`、`miniprogram-doctor/` 并列。后端是**一个 FastAPI 模块化单体**承载 4 个子系统（非 4 个仓）。PC 端的搭建另见 `admin-web/README.md`，本指南聚焦后端。

## 📋 实施阶段总览

| 阶段 | 目标 | 产出物 | 完成标准 |
| :--- | :--- | :--- | :--- |
| **一、环境与生产线** | 起 FastAPI + MySQL + Redis，AI 上下文对齐 | 目录骨架、docker-compose、.env、Alembic、`/docs` 可访问 | `uvicorn` 起服务、`/health` 通、`pytest` 跑通 |
| **二、AI 自动化开发（六步打法）** | 建模→状态机→信令→合规→签名→财务 | ORM、状态机 Service、WS 信令、Celery 上报、CA PDF、分账提现 | 各模块单测通过、Swagger 可调 |
| **三、联调/压测/等保前置** | 双端真机联调、并发压测、安全自查 | 通过的接口、修复的连接池/泄漏、等保自查项 | 状态机/支付/信令全链路自洽 |
| **四、团队协作分工** | 前后端 + 外围并行推进 | MVP 闭环 | 挂号付钱→接诊→视频→开方→进商户号 |

---

## 🛠️ 第一阶段：后端开发环境与 AI 生产线搭建

我们的核心策略是：**用 Python FastAPI 榨干服务器性能，用 Docker 搞定环境隔离，用 Gemini 批量吞吐高质代码。**

### 1. 初始化项目结构
在本地创建空的后端项目目录，并建议采用以下现代化微服务/大单体目录结构。让 AI 助手直接按照此结构生成代码：
```text
qiubei-saas-backend/
├── app/
│   ├── api/             # 接口路由层 (v1 版本)
│   ├── core/            # 全局配置、安全加密、Redis/MySQL 初始化
│   ├── models/          # SQLAlchemy 数据库模型 (ORM)
│   ├── schemas/         # Pydantic 数据校验与序列化模型
│   ├── services/        # 核心业务逻辑层 (状态机、分账、提现)
│   └── workers/         # Celery 异步任务 (卫健委数据上报、CA加签)
├── Dockerfile
├── requirements.txt
└── main.py

```
### 2. 配置 VS Code 后端插件生态

用 VS Code 打开项目目录，并安装以下生产力插件：

* **Python (Microsoft)：** 官方语法高亮、Linting、Pylance 代码提示。
* **FastAPI (Ronaldo Ramos)：** 快速生成 FastAPI 路由与组件脚手架。
* **Docker：** 方便在本地一键起 MySQL 8.0 和 Redis 7.0 镜像进行数据联调。

### 2补. 环境与工程基建（补充，避免后期返工）
* **虚拟环境与依赖：** `python -m venv .venv` + `requirements.txt` 锁定版本；不要全局装包污染环境。
* **一键起依赖：** 用 `docker-compose.yml` 起 MySQL+Redis（见 `backend/docker-compose.yml`），`.env.example` 复制为 `.env` 配置连接串（`.env` 不入库）。
* **数据库迁移：** 引入 **Alembic** 管理表结构演进（`alembic init` + 自动生成迁移），严禁手改线上表结构。
* **代码规范：** 统一 **ruff + black**（格式化/静态检查），可挂 `pre-commit`，让 AI 产出的代码风格一致、提交前自动校验。

### 3. 给 AI 智能体注入“灵魂上下文”

在开始敲代码前，将 `backend_saas_prd.md` 放入 Workspace，并在与 Gemini 对话时，先进行上下文对齐：

> **全局初始化 Prompt：**
> “你现在是精通 Python FastAPI 和医疗合规架构的资深后端专家。请阅读当前工作区内的 `backend_saas_prd.md` 文档。后续我所有的代码生成请求，你都必须严格遵循该文档的技术栈、数据库安全隔离以及订单状态机规范。理解请回复：‘逑贝后端架构师已就位’。”

---

## 🚀 第二阶段：AI 自动化开发的“六步打法”

> 原“四步”覆盖建模/状态机/合规/签名；补充**步战术 5（鉴权+WebSocket 信令）**与**步战术 6（财务分账提现）**，方能闭合 PRD 子系统 1~3。建议顺序：建模 → 鉴权 → 状态机 → 信令 → 合规网关 → 财务。每步让 AI 产出代码后立即 `pytest` + Swagger 自测。

### 🛰️ 步战术 1：AI 自动化高并发数据库建模

**提示词示例（发送给 Gemini）：**

> “请基于 `backend_saas_prd.md` 中的子系统 1 规范，编写 `app/models/order.py` 和 `app/models/prescription.py` 的 SQLAlchemy ORM 模型代码。要求状态机字段 `status` 请使用 Integer 枚举，并严格映射 PRD 中的 0~9 种状态。字段命名规范，必须包含 `created_at` 和 `updated_at` 时间戳，并给出完整的异步外键关联代码。”

### 🎨 步战术 2：白嫖 AI 编写“封闭式订单状态机”与防并发锁

**提示词示例（发送给 Gemini）：**

> “请基于 FastAPI 和 SQLAlchemy 异步上下文，编写微信支付回调的 Service 核心逻辑。需求：1. 收到回调时，使用 `SELECT ... FOR UPDATE` 悲观锁锁住对应的订单行。2. 强校验当前订单状态是否绝对为 `0 (PENDING)`。如果是，则变更为 `1 (WAITING)`；如果不是，则触发异常回滚，确保幂等性。3. 请编写完备的 `try-except` 异常捕获机制，并自动生成 5 个 Pytest 单元测试用例来模拟并发回调。”

### 🔌 步战术 3：攻坚合规网关（Celery 异步队列 + 卫健委上报）

**提示词示例（发送给 Gemini）：**

> “请基于 Python Celery 编写【子系统 4：合规对接网关】中的‘天津卫健委实时数据上报Worker’任务。要求：1. 编写一个异步任务 `task_upload_prescription_to_gov(prescription_id)`。2. 内部需实现 AES-128-CBC 加密算法对传输的 JSON 数据进行加签，HTTP Header 携带动态 Sign。3. 必须包含指数退避重试机制（Exponential Backoff）：若卫健委接口超时或返回 502，设置 `max_retries=5`，分别在 5分钟、15分钟、1小时后重试，重试失败后自动投递到死信队列并记录 Error 日志。”

### ⌨️ 步战术 4：攻坚 CA 电子签名与服务器端生成处方 PDF

**提示词示例（发送给 Gemini）：**

> “请使用 Python 的 `reportlab` 库，编写一个在服务器端动态生成标准‘电子处方单 PDF’的 Service 函数。需求：1. PDF 抬头为‘天津逑贝互联网医院电子处方单’。2. 动态渲染患者信息表、ICD-10 诊断结论、Rp 药品列表。3. 右下角利用绝对定位，将三方 CA 机构返回的医生数字签名图章和医院电子公章（PNG透明图片）完美叠加上去。请给出完整无错漏的 Python 代码。”

### 🔐 步战术 5（补充）：JWT 鉴权 + WebSocket 信令调度中心
PRD 子系统 1 的核心之一是双端实时信令，原四步未覆盖，必须补齐。
**提示词示例（发送给 Gemini）：**
> “请基于 FastAPI 实现两部分：① **JWT 鉴权依赖**：登录签发 `role`（patient/doctor/pharmacist/admin/finance）的 Token，并提供依赖注入 `require_role(...)` 做 RBAC 校验；医生端登录须校验 `doctors` 白名单。② **WebSocket 信令中心**：用 `@app.websocket('/ws')` 维护在线连接，Redis 存 `room:status:[room_id]` 与用户 SocketID；实现医生 `INIT_CALL` → 向患者推 `CALL_INVITE`，患者 `CALL_ANSWER` → 双端广播 `START_STREAM`；4 秒心跳、断线 30 秒保护期重连、超时系统挂断。请给出完整代码与并发安全处理。”

### 💰 步战术 6（补充）：财务分账与提现状态机
**提示词示例（发送给 Gemini）：**
> “请编写财务 Service：① 每笔挂号费/药费订单按比例拆分为 医院留存/医生分成/平台技术服务费 并写 `ledger`；② 提现状态机：医生发起 → 冻结余额 → Admin 人工审核 → 调微信『商家转账到零钱』→ 成功回调解冻扣减 → 归档。要求金额用『分』整数运算防精度误差，关键步骤加幂等与行锁，并给出 Pytest 用例。”

---

## 🛠️ 第三阶段：真机联调、性能捉虫与等保前置测试

### 1. 自动化接口测试（Swagger）

FastAPI 部署后，直接访问 `http://127.0.0.1:8000/docs`。这是原生自带的 Swagger 交互式文档。把这个链接发给编写前端小程序的同伴，实现“无缝零沟通成本”对接。

### 2. 借助 AI 修复高并发与内存泄漏 Bug

在进行双端真机视频对打、大流量压测时，若后端抛出数据库连接池溢出错误，直接把错误代码发给 Gemini：

> “我的 FastAPI 异步服务在压测时报了 SQLAlchemy 连接池溢出错误：[粘贴报错]。这是我的数据库初始化连接代码：[粘贴代码]。请帮我优化连接池大小（Pool Size）、最大溢出数（Max Overflow）以及连接回收机制（Pool Recycle），并指出代码中是否有未释放 Session 的地方。”

### 3. 迁移、测试与安全自查（补充）
* **数据库迁移：** 用 `alembic revision --autogenerate` 生成迁移、`alembic upgrade head` 应用，禁止手改线上表。
* **自动化测试：** `pytest` 覆盖状态机（纯逻辑免依赖即可跑，见 `backend/tests/`）、支付幂等、并发回调；接 CI（GitHub Actions）跑 lint+test。
* **WebSocket/并发压测：** 用 `locust`/`wrk` 压信令与下单接口，验证断线重连与号源锁不超卖。
* **等保三级自查：** 核对 VPC 私有子网隔离、HTTPS/WSS、密钥不硬编码、审计日志齐全、敏感字段加密存储、限流生效。

## 🏁 第四阶段：团队高效开发后端推进方案

* **研发 B（你/后端主攻）：** 坐镇 VS Code，利用本指南和 `backend_saas_prd.md`，指挥 Gemini 快速冲出核心 API 引擎、状态机、WebSocket 长连接调度和 Celery 异步 Worker 的全部代码。
* **研发 A（前端配合）：** 拿着 Swagger 接口文档，在前端小程序利用 `wx.request` 一一对接后端的挂号、接诊、看视频、开方和提现接口。
* **研发 C（外围支持）：** 负责在阿里云/腾讯云上采购满足等保三级规范的 ECS 服务器、云数据库 RDS、云缓存 Redis、以及对象存储 OSS，并配置好安全组与私有网络（VPC）隔离。

> 🖥️ **PC 管理端（admin-web）并行推进：** 药师审方、医生资质终审、药品字典、财务对账提现、监管上报面板用 Vue3 + Element Plus 实现（见 `admin-web/`）。后端为其提供 RBAC 接口；可由研发 A 在小程序间隙或独立人力并行开发。