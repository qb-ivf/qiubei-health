"""v1 路由聚合。"""
from fastapi import APIRouter

from . import (
    admin, auth, chat, consents, doctors, finance, notifications, orders, patients, prescriptions, rtc,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(patients.router)
api_router.include_router(consents.router)
api_router.include_router(doctors.router)
api_router.include_router(orders.router)
api_router.include_router(prescriptions.router)
api_router.include_router(finance.router)
api_router.include_router(notifications.router)
api_router.include_router(admin.router)
api_router.include_router(rtc.router)
api_router.include_router(chat.router)
# TODO(后续子系统)：signaling(ws) / schedule / emr / pharmacist / admin / finance / compliance
