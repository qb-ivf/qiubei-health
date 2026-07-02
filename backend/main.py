"""逑贝互联网医院 SaaS 后端入口（FastAPI）。

启动：uvicorn main:app --reload
文档：http://127.0.0.1:8000/docs
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import AsyncSessionLocal, engine
from app.models import Base  # noqa: F401  导入以填充 metadata
from app.services import compliance_service, doctor_service, order_service, tj_collector

logger = logging.getLogger("startup")


async def _expiry_sweep():
    """后台任务：每 30s 扫描并取消超 15 分钟未支付订单。"""
    while True:
        await asyncio.sleep(30)
        try:
            async with AsyncSessionLocal() as db:
                n = await order_service.cancel_expired(db)
                if n:
                    logger.info("自动取消超时订单 %s 笔", n)
        except Exception as e:  # noqa: BLE001
            logger.warning("超时扫描失败: %s", e)


async def _gov_report_sweep():
    """后台任务：每 15s 处理监管上报队列（TJ_REPORT_ENABLED 时真实发送，否则模拟）。"""
    while True:
        await asyncio.sleep(15)
        try:
            async with AsyncSessionLocal() as db:
                await compliance_service.process_pending(db)
        except Exception as e:  # noqa: BLE001
            logger.warning("监管上报扫描失败: %s", e)


async def _tj_daily_collect():
    """后台任务：每日北京时间 01:30 采集前一日终态数据入上报队列（含不良事件空签到）。"""
    while True:
        now_cn = datetime.now(tj_collector.CN_TZ)
        target = now_cn.replace(hour=1, minute=30, second=0, microsecond=0)
        if target <= now_cn:
            target += timedelta(days=1)
        await asyncio.sleep((target - now_cn).total_seconds())
        day = (datetime.now(tj_collector.CN_TZ) - timedelta(days=1)).date()
        try:
            async with AsyncSessionLocal() as db:
                counts = await tj_collector.collect_daily(db, day)
                logger.info("天津监管每日采集完成 %s: %s", day, counts)
        except Exception as e:  # noqa: BLE001
            logger.warning("天津监管每日采集失败: %s", e)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.DEBUG:
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("数据库建表完成")
            async with AsyncSessionLocal() as db:
                await doctor_service.seed_demo(db)  # 示例医生 + 号源
            logger.info("示例数据就绪")
        except Exception as e:  # noqa: BLE001
            logger.warning("初始化失败（请确认 MySQL 已启动）: %s", e)

    t1 = asyncio.create_task(_expiry_sweep())
    t2 = asyncio.create_task(_gov_report_sweep())
    t3 = asyncio.create_task(_tj_daily_collect())
    yield
    t1.cancel()
    t2.cancel()
    t3.cancel()


app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG, lifespan=lifespan)

# 跨域：DEBUG 下放开便于联调；生产用 CORS_ORIGINS 白名单（逗号分隔）收敛。
# 小程序是原生 wx.request，不受 CORS 限制；CORS 仅影响浏览器端（如 admin-web）。
_cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else _cors_origins,
    allow_credentials=not settings.DEBUG,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# 图文咨询图片：本地存储 + 静态托管（/uploads 经 Nginx 同样反代到后端）
_UPLOAD_DIR = Path(__file__).resolve().parent / "uploads"
_UPLOAD_DIR.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(_UPLOAD_DIR)), name="uploads")

# WebSocket 信令（挂在根路径 /ws）
from app.ws import router as ws_router  # noqa: E402
app.include_router(ws_router)


@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "app": settings.APP_NAME}
