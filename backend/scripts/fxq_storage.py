"""放心签签后处方卷检查、权限修复、AES-256-GCM 备份和恢复演练。"""
from __future__ import annotations

import argparse
from pathlib import Path

from app.services.fxq_archive_service import (
    FxqArchiveError,
    create_encrypted_backup,
    fix_storage_permissions,
    restore_test_encrypted_backup,
    scan_storage,
    storage_write_test,
    verify_encrypted_backup,
)


def _print_report(report) -> None:
    print(f"OK 签后处方文件 {len(report.entries)} 份，总字节 {report.total_bytes}")


def main() -> int:
    parser = argparse.ArgumentParser(description="放心签签后处方私有存储与加密归档工具")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="只读检查目录、文件权限、PDF 格式和摘要")
    check.add_argument("--write-test", action="store_true", help="创建后立即删除一个空探针，验证卷可写")
    sub.add_parser("fix-permissions", help="将存储目录/PDF mode 修复为 700/600")
    backup = sub.add_parser("backup", help="创建并立即回读校验加密归档")
    backup.add_argument("output", type=Path, help="绝对输出路径；拒绝覆盖")
    verify = sub.add_parser("verify", help="解密并校验归档，不释放 PDF")
    verify.add_argument("archive", type=Path)
    restore = sub.add_parser("restore-test", help="只恢复到已存在的空目录，禁止覆盖生产卷")
    restore.add_argument("archive", type=Path)
    restore.add_argument("target", type=Path)
    args = parser.parse_args()

    try:
        if args.command == "check":
            report = scan_storage()
            if report.errors:
                for message in report.errors:
                    print(f"[ERROR] {message}")
                return 1
            if args.write_test:
                storage_write_test()
                print("OK 处方持久卷写入探针已创建并清理")
            _print_report(report)
            return 0
        if args.command == "fix-permissions":
            report = fix_storage_permissions()
            if report.errors:
                for message in report.errors:
                    print(f"[ERROR] {message}")
                return 1
            _print_report(report)
            print("OK 存储目录/PDF 权限已修复为 700/600")
            return 0
        if args.command == "backup":
            report = create_encrypted_backup(args.output)
            print(f"OK 加密归档已创建并回读通过：{report.count} 份，总字节 {report.total_bytes}")
            return 0
        if args.command == "verify":
            report = verify_encrypted_backup(args.archive)
            print(f"OK 加密归档完整：{report.count} 份，总字节 {report.total_bytes}")
            return 0
        report = restore_test_encrypted_backup(args.archive, args.target)
        print(f"OK 恢复演练完成：{report.count} 份，总字节 {report.total_bytes}")
        return 0
    except FxqArchiveError as exc:
        print(f"[ERROR] {exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] 存储操作失败（{type(exc).__name__}），未输出处方内容")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
