"""合规网关 Worker（PRD §5.1 卫健委上报 / §5.2 CA 加签）。

严禁把上报写进主业务：主业务投递任务后立即返回，由本 Worker 异步消费，
失败走指数退避（5min/15min/1h…），仍失败入死信队列。
"""
import logging

from .celery_app import celery_app

logger = logging.getLogger("compliance")

# 指数退避：5min, 15min, 1h, 3h, 6h
BACKOFF = [300, 900, 3600, 10800, 21600]


@celery_app.task(bind=True, max_retries=len(BACKOFF))
def task_report_to_gov(self, payload: dict):
    """天津卫健委实时数据上报（AES-128-CBC + 动态 Sign）。"""
    try:
        # TODO: 1) AES-128-CBC/SM4 加密 payload
        #       2) Header 携带 Sign = MD5(Timestamp + AppSecret + Data)
        #       3) requests.post(settings.GOV_REPORT_URL, ...)
        logger.info("上报卫健委（占位）: %s", payload.get("type"))
    except Exception as exc:  # noqa: BLE001
        countdown = BACKOFF[min(self.request.retries, len(BACKOFF) - 1)]
        logger.warning("上报失败，%ss 后重试: %s", countdown, exc)
        raise self.retry(exc=exc, countdown=countdown)


@celery_app.task
def task_ca_sign_prescription(prescription_id: int):
    """防止旧调用方异步重复签署；真实签署已在药师审方事务中同步验签。"""
    raise RuntimeError(
        f"处方 {prescription_id} 禁止通过旧 Celery 任务重复签署；请使用药师审方接口"
    )
