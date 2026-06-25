"""医生常用语 / 快捷回复（问诊时快速填入病历/医嘱）。"""
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Phrase(Base, TimestampMixin):
    __tablename__ = "phrases"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)  # 医生账号 user_id
    content: Mapped[str] = mapped_column(String(255))
