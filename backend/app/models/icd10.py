"""ICD-10 疾病诊断编码字典（国家临床版 2.0，天津监管上报 S2）。

数据源：docs/specs/tianjin/国家临床版2.0疾病诊断编码（ICD-10）.xlsx（西医，约 3.6 万条）
        + 中医版（ICD-10-中医）。由 scripts/import_icd10.py 导入。
用途：医生开方时诊断从自由文本改为字典选择，落 prescriptions.icd_code/icd_name，
      供监管接口 mainDiagnoseCode/icdCode 等必输字段使用。
"""
from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Icd10Code(Base):
    __tablename__ = "icd10_codes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)   # 如 A00.000x001
    name: Mapped[str] = mapped_column(String(255), index=True)               # 疾病诊断名称
    catalog: Mapped[str] = mapped_column(String(8), default="west", index=True)  # west 西医 / tcm 中医
