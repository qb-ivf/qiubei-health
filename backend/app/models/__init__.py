"""导入所有模型，确保 Base.metadata 完整（供建表/迁移）。"""
from .audit_log import AuditLog
from .base import Base
from .drug import Drug
from .evaluation import Evaluation
from .gov_report import GovReport
from .icd10 import Icd10Code
from .ledger import Ledger
from .medical_dispute import MedicalDispute
from .message import Message
from .notification import Notification
from .order import Order
from .phrase import Phrase
from .prescription import Prescription
from .schedule import Slot
from .staff import Staff
from .user import Consent, Doctor, Patient, User
from .withdrawal import Withdrawal

__all__ = [
    "Base", "Order", "Slot", "Prescription", "Ledger", "Notification", "Drug", "Withdrawal",
    "GovReport", "User", "Patient", "Doctor", "Consent", "Staff", "Phrase", "Message", "AuditLog",
    "Icd10Code", "Evaluation", "MedicalDispute",
]
