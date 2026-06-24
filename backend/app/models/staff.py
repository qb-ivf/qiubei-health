"""运营后台员工账号（admin/pharmacist/finance 的 RBAC 登录，PRD 子系统3）。

与患者/医生(User)分离：运营后台账号由管理员通过脚本创建，密码哈希落库。
"""
from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from ..constants import Role
from .base import Base, TimestampMixin


class Staff(Base, TimestampMixin):
    __tablename__ = "staff"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default=Role.PHARMACIST)  # admin/pharmacist/finance
    name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
