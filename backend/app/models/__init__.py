"""导入所有模型，确保 Base.metadata 完整（供建表/迁移）。"""
from .base import Base
from .order import Order
from .schedule import Slot
from .user import Consent, Doctor, Patient, User

__all__ = ["Base", "Order", "Slot", "User", "Patient", "Doctor", "Consent"]
