"""导入国家临床版 2.0 ICD-10 编码表到 icd10_codes（天津监管 S2）。重复执行安全（按 code 幂等）。

数据源（已随仓库归档）：
  docs/specs/tianjin/国家临床版2.0疾病诊断编码（ICD-10）.xlsx        → catalog=west
  docs/specs/tianjin/国家临床版2.0中医疾病诊断编码（ICD-10-中医）.xlsx → catalog=tcm

用法（backend 目录）：
  pip install openpyxl
  python -m scripts.import_icd10            # 首次全量导入（表非空则跳过）
  python -m scripts.import_icd10 --force    # 清空重导
服务器（docker）：
  docker compose ... exec api python -m scripts.import_icd10
"""
import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy import delete, func, insert, select

from app.core.database import engine
from app.models.icd10 import Icd10Code

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SOURCES = [
    (REPO_ROOT / "docs/specs/tianjin/国家临床版2.0疾病诊断编码（ICD-10）.xlsx", "west"),
    (REPO_ROOT / "docs/specs/tianjin/国家临床版2.0中医疾病诊断编码（ICD-10-中医）.xlsx", "tcm"),
]
BATCH = 2000


def _read_rows(path: Path, catalog: str) -> list[dict]:
    import openpyxl

    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.worksheets[0]
    rows, seen = [], set()
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 0:  # 表头：疾病诊断编码 | 疾病诊断名称
            continue
        code = str(row[0]).strip() if row[0] else ""
        name = str(row[1]).strip() if len(row) > 1 and row[1] else ""
        if not code or not name or code in seen:
            continue
        seen.add(code)
        rows.append({"code": code[:32], "name": name[:255], "catalog": catalog})
    wb.close()
    return rows


async def main(force: bool) -> None:
    async with engine.begin() as conn:
        count = await conn.scalar(select(func.count(Icd10Code.id)))
        if count and not force:
            print(f"icd10_codes 已有 {count} 条，跳过（--force 清空重导）")
            await engine.dispose()
            return
        if count and force:
            await conn.execute(delete(Icd10Code))
            print(f"已清空 {count} 条")

        total = 0
        for path, catalog in SOURCES:
            if not path.exists():
                print(f"跳过（文件不存在）: {path}")
                continue
            rows = _read_rows(path, catalog)
            for i in range(0, len(rows), BATCH):
                await conn.execute(insert(Icd10Code), rows[i : i + BATCH])
            total += len(rows)
            print(f"导入 {catalog}: {len(rows)} 条  ← {path.name}")
        print(f"完成，共 {total} 条")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="清空后重新导入")
    args = parser.parse_args()
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        sys.exit("缺少 openpyxl：pip install openpyxl")
    asyncio.run(main(args.force))
