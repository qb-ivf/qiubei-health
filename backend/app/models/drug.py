"""院内药品字典（PRD §4.2）。特殊限售药强制标记并拦截开方。"""
from sqlalchemy import BigInteger, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Drug(Base, TimestampMixin):
    __tablename__ = "drugs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), index=True)
    spec: Mapped[str | None] = mapped_column(String(64), nullable=True)
    price_fen: Mapped[int] = mapped_column(Integer, default=0)
    category: Mapped[str] = mapped_column(String(16), default="处方药")  # 处方药/非处方药/特殊限售药
    restricted: Mapped[bool] = mapped_column(Boolean, default=False)
