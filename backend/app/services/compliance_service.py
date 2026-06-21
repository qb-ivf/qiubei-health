"""合规网关服务（PRD §5，M9 占位实现）。

卫健委上报：本地异步队列（GovReport 表）+ 后台 sweeper 模拟上报 + 重试/死信。
生产改用 Celery Worker（见 workers/compliance.py 骨架）+ AES/SM4 加密 + 动态 Sign。
CA 加签为占位；处方 PDF 用 reportlab 真实生成（红章占位）。
"""
import io
import random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.gov_report import GovReport

# 指数退避（生产用；本地 sweeper 演示忽略时间间隔）
BACKOFF = [300, 900, 3600, 10800, 21600]
MAX_RETRY = len(BACKOFF)


async def enqueue(db: AsyncSession, biz_type: str, biz_id: int):
    db.add(GovReport(biz_type=biz_type, biz_id=biz_id, status="pending"))
    await db.flush()


async def process_pending(db: AsyncSession) -> int:
    """后台扫描：模拟向卫健委上报（AES/SM4+Sign），失败重试，超限入死信。"""
    res = await db.execute(
        select(GovReport).where(GovReport.status.in_(["pending", "failed"])).limit(50)
    )
    reports = list(res.scalars().all())
    for r in reports:
        ok = random.random() > 0.2  # 模拟 80% 成功
        r.latency_ms = random.randint(80, 500)
        if ok:
            r.status = "success"
            r.last_error = None
        else:
            r.retries += 1
            if r.retries >= MAX_RETRY:
                r.status = "dead"
                r.last_error = "卫健委网关多次失败，已入死信队列"
            else:
                r.status = "failed"
                r.last_error = "卫健委网关 502 / 响应超时"
    if reports:
        await db.commit()
    return len(reports)


async def stats(db: AsyncSession) -> dict:
    total = await db.scalar(select(func.count(GovReport.id))) or 0
    success = await db.scalar(select(func.count(GovReport.id)).where(GovReport.status == "success")) or 0
    failed = await db.scalar(
        select(func.count(GovReport.id)).where(GovReport.status.in_(["failed", "dead"]))
    ) or 0
    avg = await db.scalar(select(func.coalesce(func.avg(GovReport.latency_ms), 0))) or 0
    return {"total": int(total), "success": int(success), "failed": int(failed), "avg_ms": int(avg)}


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
        await db.commit()
    return r


def generate_prescription_pdf(rx, patient_name: str, doctor_name: str) -> bytes:
    """reportlab 生成处方 PDF（中文用内置 STSong-Light；CA 红章为占位）。"""
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
    c.drawString(50, y - 20, f"数字签名：{rx.ca_sign or '已CA加签'}（占位，M9 接正式 SM2）")
    c.setFillColorRGB(0.73, 0.1, 0.1)
    c.drawString(360, y - 20, "【互联网医院处方专用章】")
    c.save()
    buf.seek(0)
    return buf.read()
