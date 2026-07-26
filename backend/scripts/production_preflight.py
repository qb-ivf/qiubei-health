"""生产环境基础安全只读预检。

用法：
  python -m scripts.production_preflight

不写数据库、不请求外网、不输出密钥。存在 FAIL 时退出码为 1；WARN 不阻断。
"""
from app.core.config import settings
from app.services.production_readiness import configuration_checks


def main() -> int:
    checks = configuration_checks(settings)
    for item in checks:
        print(f"{item.level} [{item.area}] {item.message}")
    fail_count = sum(item.level == "FAIL" for item in checks)
    warn_count = sum(item.level == "WARN" for item in checks)
    print(f"SUMMARY FAIL={fail_count} WARN={warn_count}")
    return 1 if fail_count else 0


if __name__ == "__main__":
    raise SystemExit(main())
