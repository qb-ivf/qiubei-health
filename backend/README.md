# backend · 逑贝互联网医院 SaaS 中央服务端（FastAPI）

模块化单体（modular monolith），承载 PRD 的四大子系统：核心 API 引擎、医生端工作台后台、运营总管理后台、合规对接网关。详见 [docs/backend_saas_prd.md](../docs/backend_saas_prd.md)。

## 目录结构

```
backend/
├── app/
│   ├── api/v1/        # 接口路由层（orders / rtc / …）
│   ├── core/          # 配置 · 数据库 · Redis · 安全(JWT/脱敏)
│   ├── models/        # SQLAlchemy ORM
│   ├── schemas/       # Pydantic 校验/序列化
│   ├── services/      # 业务逻辑（订单状态机 / 分账 / 提现）
│   ├── workers/       # Celery 异步任务（卫健委上报 / CA 加签）
│   └── constants.py   # 订单状态机枚举 + 信令 + 角色
├── tests/             # pytest（状态机纯逻辑测试免依赖）
├── main.py · Dockerfile · docker-compose.yml · requirements.txt
```

## 本地启动

### 方式 A：全 Docker 一键起（推荐，Windows + Docker Desktop）
无需本地装 Python。在 `backend/` 目录执行：
```powershell
docker compose up -d --build      # 起 MySQL + Redis + api（自动建表）
# 访问 http://127.0.0.1:8000/docs  与  /health
docker compose logs -f api        # 看后端日志
docker compose down               # 停止（加 -v 连数据卷一起删）
```
改了代码会自动热重载（源码已挂载进容器）。改了 `requirements.txt` 才需 `--build` 重建。

### 方式 B：本地 Python（依赖只起 DB）
```powershell
copy .env.example .env
docker compose up -d mysql redis  # 只起数据库
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --reload         # http://127.0.0.1:8000/docs
pytest -q                         # 纯逻辑测试（状态机/鉴权）免 DB 即可跑
```
> 建议用 Python 3.11/3.12（部分依赖在 3.14 上可能缺预编译包）。

## 已落地（脚手架）

- 订单**封闭式状态机**（`constants.ALLOWED_TRANSITIONS`）+ 悲观锁/幂等回调（`services/order_service.py`）
- 微信支付回调、医生接诊接口（`api/v1/orders.py`）
- RTC `UserSig` 动态下发骨架（`api/v1/rtc.py`）
- 合规网关 Worker：卫健委上报指数退避、CA 加签占位（`workers/compliance.py`）

> 后续按 `docs/backend_saas_guide.md` 的五步打法扩展：JWT 鉴权、WebSocket 信令、药师审方、财务分账提现、合规网关落地。
