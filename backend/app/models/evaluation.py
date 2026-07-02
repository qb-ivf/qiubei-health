"""患者评价（天津监管 2.4.1 uploadBusinessInfoAfter 数据源，S2）。

监管映射：evaluateID=id、bussID=订单 order_no、businessType 由 consult_type 推导
（text→1 图文咨询 / video→4 在线复诊）、医生与科室信息经 doctor_id 关联取得。
"""
from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Evaluation(Base, TimestampMixin):
    __tablename__ = "evaluations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)  # 一单一评
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)                # 评价账号
    doctor_id: Mapped[int] = mapped_column(BigInteger, index=True)              # 被评医生
    satisfaction: Mapped[int] = mapped_column(Integer)                          # 1-5（1 非常不满意 … 5 非常满意）
    scoring: Mapped[int] = mapped_column(Integer)                               # 0-10 分
    content: Mapped[str] = mapped_column(String(300))                           # 评价内容（监管必输）
    complaints: Mapped[str | None] = mapped_column(String(1024), nullable=True) # 投诉建议
    evaluator: Mapped[str | None] = mapped_column(String(30), nullable=True)    # 评价人（就诊人姓名）
