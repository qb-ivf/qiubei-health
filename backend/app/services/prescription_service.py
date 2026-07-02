"""处方服务（M5）：开方提交 / 药师审方 / 驳回 + 特殊药拦截。"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..constants import OrderStatus
from ..models.order import Order
from ..models.prescription import Prescription
from ..schemas.prescription import PrescriptionCreate
from . import order_service

# 互联网医院严禁开具的特殊管理药（PRD §4.2）。生产应由药品字典 restricted 标记驱动。
SPECIAL_DRUG_KEYWORDS = ["哌替啶", "吗啡", "芬太尼", "氯胺酮", "地西泮注射", "可待因", "苯巴比妥"]


class RxError(Exception):
    """处方业务异常。"""


def _check_special(items: list) -> None:
    for it in items:
        name = (it.name if hasattr(it, "name") else it.get("name", "")) or ""
        if any(k in name for k in SPECIAL_DRUG_KEYWORDS):
            raise RxError(f"合规限制：本院不支持开具特殊管理药品「{name}」")


async def submit(db: AsyncSession, doctor_uid: int, data: PrescriptionCreate) -> Prescription:
    """医生开方提交：病历校验 + 特殊药拦截 + 订单 2→3（或驳回后 4→3）。"""
    if not data.diagnosis or len(data.diagnosis.strip()) < 2:
        raise RxError("初步诊断不能为空")
    _check_special(data.items)

    order = await db.get(Order, data.order_id)
    if order is None:
        raise RxError("订单不存在")

    cur = OrderStatus(order.status)
    if cur == OrderStatus.CONSULTING:
        await order_service.transition(db, order.id, OrderStatus.AUDITING, expect_from=OrderStatus.CONSULTING)
    elif cur == OrderStatus.REJECTED:
        await order_service.transition(db, order.id, OrderStatus.AUDITING, expect_from=OrderStatus.REJECTED)
    else:
        raise RxError(f"当前订单状态 {cur.name} 不可开方")

    # 复用同订单的处方记录（驳回重开时更新）
    res = await db.execute(select(Prescription).where(Prescription.order_id == order.id))
    rx = res.scalars().first()
    if rx is None:
        rx = Prescription(order_id=order.id, doctor_id=order.doctor_id, patient_id=order.patient_id)
        db.add(rx)

    rx.chief = data.chief
    rx.present_illness = data.present_illness
    rx.diagnosis = data.diagnosis
    rx.icd_code = data.icd_code
    rx.icd_name = data.icd_name
    rx.advice = data.advice
    rx.items = [it.model_dump() for it in data.items]
    rx.audit_status = "pending"
    rx.reject_reason = None
    await db.flush()
    return rx


async def list_pending(db: AsyncSession) -> list[Prescription]:
    res = await db.execute(select(Prescription).where(Prescription.audit_status == "pending").order_by(Prescription.id.asc()))
    return list(res.scalars().all())


async def approve(db: AsyncSession, rx_id: int) -> Prescription:
    """药师审核通过：订单 3→5 + CA 加签（占位，M9 接真实 SM2）。"""
    rx = await db.get(Prescription, rx_id)
    if rx is None or rx.audit_status != "pending":
        raise RxError("处方不存在或已处理")
    await order_service.transition(db, rx.order_id, OrderStatus.PRESCRIBED, expect_from=OrderStatus.AUDITING)
    rx.audit_status = "approved"
    rx.ca_sign = "CA_MOCK_SIGN"               # TODO(M9): 调 CA 云端 SM2 加签
    rx.pdf_url = f"/rx/{rx.order_id}.pdf"      # TODO(M9): reportlab 生成盖章 PDF → OSS

    # 审核通过后计算药费，落到订单（M6 药费支付用）
    order = await db.get(Order, rx.order_id)
    if order is not None:
        order.drug_fee_fen = sum(int(it.get("price_fen", 0)) * int(it.get("qty", 1)) for it in (rx.items or []))
        from . import notification_service
        await notification_service.notify(
            db, order.user_id, "rx", "处方已通过", "药师审核通过，请尽快缴纳药费", order.id
        )
    await db.flush()
    return rx


async def reject(db: AsyncSession, rx_id: int, reason: str) -> Prescription:
    """药师驳回：订单 3→4 + 驳回理由。"""
    rx = await db.get(Prescription, rx_id)
    if rx is None or rx.audit_status != "pending":
        raise RxError("处方不存在或已处理")
    if not reason.strip():
        raise RxError("驳回原因不能为空")
    await order_service.transition(db, rx.order_id, OrderStatus.REJECTED, expect_from=OrderStatus.AUDITING)
    rx.audit_status = "rejected"
    rx.reject_reason = reason
    await db.flush()
    return rx


async def get_by_order(db: AsyncSession, order_id: int) -> Prescription | None:
    res = await db.execute(select(Prescription).where(Prescription.order_id == order_id))
    return res.scalars().first()
