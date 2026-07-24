"""合规网关服务（天津监管 S3 + 处方 PDF）。

上报队列：业务侧 enqueue（幂等，payload 入队时快照）→ 后台 sweeper 消费：
  - TJ_REPORT_ENABLED=true 且网关配置齐 → tj_gateway 真实发送（SM4/SM3）；
  - 否则本地模拟成功（开发环境闭环不变）。
失败分类：网络/系统繁忙/请求过期 → 指数退避自动重试，超限入死信；
数据错误（-99 等）→ 直接入死信，改数后在后台手工重报。
CA 文档签署接口仍待供应商文档；处方 PDF 仅生成明确标识的未签名预览，
不再绘制会被误认为有效电子签章的红章。
"""
import io
import logging
import time as _time
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.gov_report import GovReport
from .tj_config import gateway_config_errors

logger = logging.getLogger(__name__)

# 指数退避（秒）：5min / 15min / 1h / 3h / 6h
BACKOFF = [300, 900, 3600, 10800, 21600]
MAX_RETRY = len(BACKOFF)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def enqueue(
    db: AsyncSession,
    biz_type: str,
    biz_id: int,
    method: str | None = None,
    payload: list | None = None,
    batch_date: date | None = None,
    refresh: bool = False,
) -> GovReport:
    """幂等入队：(biz_type, biz_id) 已存在则跳过；refresh=True 时刷新 payload 并重置重发
    （用于药品目录更新、不良事件当日签到等需覆盖旧任务的场景）。"""
    res = await db.execute(
        select(GovReport).where(GovReport.biz_type == biz_type, GovReport.biz_id == biz_id)
    )
    existing = res.scalars().first()
    if existing:
        if refresh:
            existing.method = method or existing.method
            if payload is not None:
                existing.payload = payload
            existing.batch_date = batch_date or existing.batch_date
            existing.status = "pending"
            existing.retries = 0
            existing.next_retry_at = None
            existing.latency_ms = 0
            existing.msg_code = None
            existing.resp_msg = None
            existing.last_error = None
            await db.flush()
        return existing
    r = GovReport(
        biz_type=biz_type, biz_id=biz_id, method=method, payload=payload,
        batch_date=batch_date, status="pending",
    )
    db.add(r)
    await db.flush()
    return r


def _gateway_ready() -> bool:
    return bool(settings.TJ_REPORT_ENABLED and not gateway_config_errors(settings))


async def process_pending(db: AsyncSession) -> int:
    """后台扫描：发送 pending 与到达退避时间的 failed 任务。"""
    # 正式环境关停上报时必须保留队列，不能把待发数据伪装成“模拟成功”。
    # DEBUG 开发环境继续维持原有模拟闭环；若显式打开了开关但配置不完整，也绝不模拟。
    if not _gateway_ready() and (not settings.DEBUG or settings.TJ_REPORT_ENABLED):
        if settings.TJ_REPORT_ENABLED:
            logger.error("天津监管上报已开启但配置不完整：%s", "; ".join(gateway_config_errors(settings)))
        return 0

    now = _utcnow()
    res = await db.execute(
        select(GovReport)
        .where(
            (GovReport.status == "pending")
            | ((GovReport.status == "failed") & ((GovReport.next_retry_at.is_(None)) | (GovReport.next_retry_at <= now)))
        )
        # 平台要求药品基础目录先于处方等业务数据备案；正式首批也按此优先级发送。
        .order_by(case((GovReport.biz_type == "drug", 0), else_=1), GovReport.id.asc())
        .limit(20)
    )
    reports = list(res.scalars().all())
    for r in reports:
        await _send_one(r)
    if reports:
        await db.commit()
    return len(reports)


async def _send_one(r: GovReport) -> None:
    if not r.method or r.payload is None:
        # 无 payload 的历史/占位任务：直接标记成功，不再模拟随机失败
        r.status, r.msg_code, r.resp_msg = "success", None, "占位任务（无 payload，未发送）"
        return

    if not _gateway_ready() and settings.DEBUG and not settings.TJ_REPORT_ENABLED:
        r.status, r.msg_code, r.latency_ms = "success", 200, 0
        r.resp_msg = "本地模拟成功（TJ_REPORT_ENABLED=false）"
        return
    if not _gateway_ready():
        # 双保险：配置异常时保持 pending，等待运维修正，不能吞掉任务。
        r.last_error = "监管网关未启用或配置不完整，任务保持待发送"
        return

    from . import tj_gateway  # 局部导入避免循环
    t0 = _time.monotonic()
    result = await tj_gateway.tj_call(r.method, r.payload)
    r.latency_ms = int((_time.monotonic() - t0) * 1000)
    r.msg_code = result.msg_code
    r.resp_msg = (result.msg or "")[:500]
    if result.ok:
        r.status, r.last_error, r.next_retry_at = "success", None, None
    elif result.retryable:
        r.retries += 1
        if r.retries >= MAX_RETRY:
            r.status = "dead"
            r.last_error = f"重试 {MAX_RETRY} 次仍失败：{result.msg}"[:255]
        else:
            r.status = "failed"
            r.next_retry_at = _utcnow() + timedelta(seconds=BACKOFF[r.retries - 1])
            r.last_error = f"可重试失败（第{r.retries}次）：{result.msg}"[:255]
    else:
        # 数据错误（-99 字段缺失等）：自动重试无意义，入死信待人工改数后重报
        r.status = "dead"
        r.last_error = f"数据错误：{result.msg}"[:255]


async def stats(db: AsyncSession) -> dict:
    total = await db.scalar(select(func.count(GovReport.id))) or 0
    success = await db.scalar(select(func.count(GovReport.id)).where(GovReport.status == "success")) or 0
    failed = await db.scalar(
        select(func.count(GovReport.id)).where(GovReport.status.in_(["failed", "dead"]))
    ) or 0
    avg = await db.scalar(select(func.coalesce(func.avg(GovReport.latency_ms), 0))) or 0

    # 按接口方法维度的统计（S4 面板）
    res = await db.execute(
        select(GovReport.method, GovReport.status, func.count(GovReport.id))
        .where(GovReport.method.is_not(None))
        .group_by(GovReport.method, GovReport.status)
    )
    by_method: dict[str, dict] = {}
    for method, status, cnt in res.all():
        m = by_method.setdefault(method, {"method": method, "total": 0, "success": 0, "failed": 0, "dead": 0, "pending": 0})
        m["total"] += int(cnt)
        if status in m:
            m[status] += int(cnt)

    # 最近一次不良事件签到（每日强制）
    res = await db.execute(
        select(GovReport).where(GovReport.biz_type == "dispute_signin").order_by(GovReport.id.desc()).limit(1)
    )
    signin = res.scalars().first()
    return {
        "total": int(total), "success": int(success), "failed": int(failed), "avg_ms": int(avg),
        "enabled": _gateway_ready(),
        "by_method": sorted(by_method.values(), key=lambda x: x["method"]),
        "signin": {"batch_date": str(signin.batch_date) if signin.batch_date else None,
                   "status": signin.status} if signin else None,
    }


async def list_failed(db: AsyncSession) -> list[GovReport]:
    res = await db.execute(
        select(GovReport).where(GovReport.status.in_(["failed", "dead"])).order_by(GovReport.id.desc())
    )
    return list(res.scalars().all())


async def retry(db: AsyncSession, rid: int):
    r = await db.get(GovReport, rid)
    if r:
        r.status = "pending"
        r.retries = 0
        r.next_retry_at = None
        await db.commit()
    return r


def generate_prescription_pdf(rx, patient_name: str, doctor_name: str) -> bytes:
    """reportlab 生成处方 PDF。

    ca_sign 为空时输出醒目的“未完成数字签名”提示，不得作为有效电子处方。
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.pdfgen import canvas

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    c.setFont("STSong-Light", 18)
    c.drawCentredString(w / 2, h - 60, "天津逑贝互联网医院电子处方笺")
    c.setFont("STSong-Light", 11)
    c.drawString(50, h - 100, f"姓名：{patient_name}")
    c.drawString(320, h - 100, "科室：呼吸内科")
    c.drawString(50, h - 122, f"临床诊断：{rx.diagnosis or ''}")

    y = h - 160
    c.drawString(50, y, "Rp（治疗建议）：")
    y -= 22
    for it in (rx.items or []):
        c.drawString(70, y, f"{it.get('name')}  x{it.get('qty', 1)}   用法：{it.get('usage', '')}")
        y -= 18

    y -= 24
    c.drawString(50, y, f"开方医师：{doctor_name}        审核药师：（已审核）")
    if rx.ca_sign:
        c.drawString(50, y - 20, f"数字签名：{rx.ca_sign}")
    else:
        c.setFillColorRGB(0.73, 0.1, 0.1)
        c.drawString(50, y - 20, "未完成文档数字签名——仅供开发预览，不可作为有效电子处方")
    c.save()
    buf.seek(0)
    return buf.read()
