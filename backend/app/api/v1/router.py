"""v1 路由聚合。"""
from fastapi import APIRouter

from . import orders, rtc

api_router = APIRouter()
api_router.include_router(orders.router)
api_router.include_router(rtc.router)
# TODO(后续子系统)：auth / signaling(ws) / schedule / emr / pharmacist / admin / finance / compliance
