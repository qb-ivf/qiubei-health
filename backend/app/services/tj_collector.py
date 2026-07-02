"""天津监管每日采集器（S3）：按北京时间日界扫描前一日终态业务数据 → 组包入 gov_reports 队列。

调度：main.py 每日北京时间 01:30 触发 collect_daily(昨日)；admin 亦可按日手工补采。
幂等：enqueue 以 (biz_type, biz_id) 去重，重复采集同一天不会产生重复任务；
      不良事件签到（dispute_signin）按日 refresh，当日无事件也发空数组（规范强制）。
"""
import base64
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import OrderStatus
from ..models.evaluation import Evaluation
from ..models.medical_dispute import MedicalDispute
from ..models.order import Order
from ..models.prescription import Prescription
from ..models.staff import Staff
from ..models.user import Doctor, Patient
from . import compliance_service, tj_mappers

logger = logging.getLogger(__name__)

_UPLOAD_ROOT = Path(__file__).resolve().parents[2] / "uploads"  # backend/uploads

CN_TZ = timezone(timedelta(hours=8))
_TERMINAL = (int(OrderStatus.FINISHED), int(OrderStatus.REFUNDED), int(OrderStatus.CANCELLED))


def _window(day_cn: date) -> tuple[datetime, datetime]:
    """北京时间某日 [00:00, 24:00) → naive UTC 区间（与库内时间基准一致）。"""
    start = datetime(day_cn.year, day_cn.month, day_cn.day, tzinfo=CN_TZ)
    to_utc = lambda dt: dt.astimezone(timezone.utc).replace(tzinfo=None)  # noqa: E731
    return to_utc(start), to_utc(start + timedelta(days=1))


async def _order_ctx(db: AsyncSession, order: Order):
    patient = await db.get(Patient, order.patient_id)
    doctor = await db.get(Doctor, order.doctor_id)
    res = await db.execute(select(Prescription).where(Prescription.order_id == order.id))
    rx = res.scalars().first()
    return patient, doctor, rx


async def _resolve_first_diagnosis(order: Order) -> None:
    """首诊材料本地文件 → 监管附件 id（uploadFile）。网关未启用时保持本地路径（映射层会置空外发）。"""
    from . import tj_gateway
    value = order.first_diagnosis_file_ids or ""
    if "/uploads/" not in value or not compliance_service._gateway_ready():
        return
    ids: list[str] = []
    for p in value.split(","):
        p = p.strip()
        if not p.startswith("/uploads/"):
            ids.append(p)  # 已是附件 id
            continue
        f = _UPLOAD_ROOT / p.removeprefix("/uploads/")
        if not f.exists():
            logger.warning("首诊材料文件缺失 order=%s path=%s", order.id, p)
            continue
        content = f.read_bytes()
        result = await tj_gateway.tj_upload_file(
            f.name, base64.b64encode(content).decode(), str(len(content)), f.suffix.lstrip(".") or "jpg"
        )
        if result.ok and result.data:
            ids.extend(str(x) for x in result.data)
        else:
            logger.warning("首诊材料上传失败 order=%s: %s", order.id, result.msg)
            return  # 保留本地路径，下个批次重试
    order.first_diagnosis_file_ids = ",".join(ids)[:300]


async def collect_daily(db: AsyncSession, day_cn: date) -> dict:
    """采集北京时间 day_cn 当日到达终态的数据，入队。返回各类计数。"""
    start, end = _window(day_cn)
    counts = {"consult": 0, "referral": 0, "emr": 0, "recipe": 0, "verification": 0,
              "evaluation": 0, "dispute": 0}

    # 1) 终态订单：图文 → 在线咨询；视频 → 在线复诊 + 电子病历
    res = await db.execute(
        select(Order).where(
            Order.status.in_(_TERMINAL), Order.finished_at >= start, Order.finished_at < end
        )
    )
    for order in res.scalars().all():
        if order.status == int(OrderStatus.CANCELLED) and order.paid_at is None:
            continue  # 未支付即取消：诊疗业务未成立，不上报
        patient, doctor, rx = await _order_ctx(db, order)
        if order.consult_type == "text":
            await compliance_service.enqueue(
                db, "consult", order.id, "uploadConsultIndicators",
                [tj_mappers.build_consult(order, patient, doctor, rx)], day_cn,
            )
            counts["consult"] += 1
        else:
            await _resolve_first_diagnosis(order)  # 首诊材料换监管附件 id（网关可用时）
            await compliance_service.enqueue(
                db, "referral", order.id, "uploadReferralIndicators",
                [tj_mappers.build_referral(order, patient, doctor, rx)], day_cn,
            )
            counts["referral"] += 1
            if rx is not None:
                await compliance_service.enqueue(
                    db, "emr", rx.id, "uploadElectMedicalRecord",
                    [tj_mappers.build_emr(order, patient, doctor, rx)], day_cn,
                )
                counts["emr"] += 1

    # 2) 当日审方通过的处方
    res = await db.execute(
        select(Prescription).where(
            Prescription.audit_status == "approved",
            Prescription.checked_at >= start, Prescription.checked_at < end,
        )
    )
    for rx in res.scalars().all():
        order = await db.get(Order, rx.order_id)
        if order is None:
            continue
        patient = await db.get(Patient, rx.patient_id)
        doctor = await db.get(Doctor, rx.doctor_id)
        pharmacist = await db.get(Staff, rx.audit_staff_id) if rx.audit_staff_id else None
        await compliance_service.enqueue(
            db, "recipe", rx.id, "uploadRecipeIndicators",
            [tj_mappers.build_recipe(order, patient, doctor, rx, pharmacist)], day_cn,
        )
        counts["recipe"] += 1

    # 3) 当日药费支付完成（核销）的订单
    res = await db.execute(
        select(Order).where(
            Order.status == int(OrderStatus.FINISHED), Order.drug_fee_fen > 0,
            Order.finished_at >= start, Order.finished_at < end,
        )
    )
    for order in res.scalars().all():
        rxres = await db.execute(select(Prescription).where(Prescription.order_id == order.id))
        rx = rxres.scalars().first()
        if rx is None or rx.audit_status != "approved":
            continue
        await compliance_service.enqueue(
            db, "verification", order.id, "uploadRecipeVerificationIndicators",
            [tj_mappers.build_verification(order, rx)], day_cn,
        )
        counts["verification"] += 1

    # 4) 当日新增评价
    res = await db.execute(
        select(Evaluation).where(Evaluation.created_at >= start, Evaluation.created_at < end)
    )
    for ev in res.scalars().all():
        order = await db.get(Order, ev.order_id)
        doctor = await db.get(Doctor, ev.doctor_id)
        await compliance_service.enqueue(
            db, "evaluation", ev.id, "uploadBusinessInfoAfter",
            [tj_mappers.build_evaluation(ev, order, doctor)], day_cn,
        )
        counts["evaluation"] += 1

    # 5) 不良事件每日签到（强制：无事件也发空数组）
    res = await db.execute(
        select(MedicalDispute).where(
            MedicalDispute.created_at >= start, MedicalDispute.created_at < end
        )
    )
    disputes = list(res.scalars().all())
    await compliance_service.enqueue(
        db, "dispute_signin", int(day_cn.strftime("%Y%m%d")), "pushMedicalDispute",
        [tj_mappers.build_dispute(d) for d in disputes], day_cn, refresh=True,
    )
    counts["dispute"] = len(disputes)

    await db.commit()
    logger.info("天津监管采集 %s: %s", day_cn, counts)
    return counts
