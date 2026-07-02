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

    # —— 天津监管药品目录备案字段（2.1.1，S0 T6 对照后由 admin 补录）——
    drug_class: Mapped[str | None] = mapped_column(String(50), nullable=True)     # 监管药品分类代码（字典 3.10）
    countrydrcode: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 国家药品编码
    packing: Mapped[str | None] = mapped_column(String(30), nullable=True)        # 包装规格（如 0.25g*24粒）
    manufacturer: Mapped[str | None] = mapped_column(String(60), nullable=True)   # 产地/生产商
    use_flag: Mapped[str] = mapped_column(String(1), default="1")                 # 1 有效 2 取消
