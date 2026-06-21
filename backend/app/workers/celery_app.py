"""Celery 应用（合规网关异步上报、CA 加签等，PRD §5）。"""
from celery import Celery

from ..core.config import settings

celery_app = Celery(
    "qiubei",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    task_acks_late=True,
)
