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
from app.core.database import AsyncSessionLocal
from app.core.redis import redis_client
from app.services import compliance_service, doctor_service, order_service, tj_collector
from app.services.task_lease import distributed_lease

logger = logging.getLogger("startup")


async def _expiry_sweep():
    """后台任务：每 30s 扫描并取消超 15 分钟未支付订单。"""
    while True:
        await asyncio.sleep(30)
        try:
            async with distributed_lease("cancel-expired", 60) as acquired:
                if not acquired:
                    continue
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
            async with distributed_lease("gov-report-sweep", 60) as acquired:
                if not acquired:
                    continue
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
        # 多实例中未取得租约的实例继续轮询；租约持有者异常时，其他实例可在
        # 租约到期后接管。完成标记保证同一批次不会重复采集。
        for _ in range(180):
            try:
                result = await _collect_tj_day_once(day)
                if result in {"completed", "already_completed"}:
                    break
            except Exception as e:  # noqa: BLE001
                logger.warning("天津监管每日采集失败，将重试: %s", e)
            await asyncio.sleep(60)
        else:
            logger.error("天津监管每日采集连续 3 小时未完成: %s", day)


async def _collect_tj_day_once(day) -> str:
    """尝试采集单日批次，返回 completed/already_completed/busy。"""
    done_key = f"task:done:tj-daily-collect:{day.isoformat()}"
    if await redis_client.exists(done_key):
        return "already_completed"
    async with distributed_lease(f"tj-daily-collect:{day.isoformat()}", 900) as acquired:
        if not acquired:
            return "busy"
        if await redis_client.exists(done_key):
            return "already_completed"
        async with AsyncSessionLocal() as db:
            counts = await tj_collector.collect_daily(db, day)
        await redis_client.set(done_key, "1", ex=3 * 24 * 60 * 60)
        logger.info("天津监管每日采集完成 %s: %s", day, counts)
        return "completed"


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.DEBUG:
        try:
            async with AsyncSessionLocal() as db:
                await doctor_service.seed_demo(db)  # 示例医生 + 号源
            logger.info("示例数据就绪")
        except Exception as e:  # noqa: BLE001
            logger.warning("开发示例数据初始化失败（请确认已执行 db_upgrade）: %s", e)

    t1 = asyncio.create_task(_expiry_sweep())
    t2 = asyncio.create_task(_gov_report_sweep())
    t3 = asyncio.create_task(_tj_daily_collect())
    from app.ws import manager as ws_manager

    await ws_manager.start()
    try:
        yield
    finally:
        t1.cancel()
        t2.cancel()
        t3.cancel()
        await asyncio.gather(t1, t2, t3, return_exceptions=True)
        await ws_manager.stop()


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

# 小程序自托管图标字体：固定子集，不依赖第三方 CDN。
_STATIC_DIR = Path(__file__).resolve().parent / "app" / "static"
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")

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
