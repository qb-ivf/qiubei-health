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

```bash
cp .env.example .env
docker compose up -d            # 起 MySQL + Redis
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
uvicorn main:app --reload       # http://127.0.0.1:8000/docs
celery -A app.workers.celery_app.celery_app worker -l info   # 另开一个终端跑 Worker
pytest                          # 跑状态机测试
```

## 已落地（脚手架）

- 订单**封闭式状态机**（`constants.ALLOWED_TRANSITIONS`）+ 悲观锁/幂等回调（`services/order_service.py`）
- 微信支付回调、医生接诊接口（`api/v1/orders.py`）
- RTC `UserSig` 动态下发骨架（`api/v1/rtc.py`）
- 合规网关 Worker：卫健委上报指数退避、CA 加签占位（`workers/compliance.py`）

> 后续按 `docs/backend_saas_guide.md` 的五步打法扩展：JWT 鉴权、WebSocket 信令、药师审方、财务分账提现、合规网关落地。
