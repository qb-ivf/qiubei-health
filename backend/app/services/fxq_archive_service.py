"""放心签签后处方 PDF 的私有存储检查与 AES-256-GCM 加密归档。

归档格式为自描述版本头 + nonce + 加密的 tar.gz 流 + GCM tag。工作过程中不会把
未加密 tar 文件写入磁盘。恢复功能只允许写入一个已存在的空目录，不直接覆盖生产卷。
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import stat
import tarfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from ..core.config import settings
from .fxq_document_service import _storage_root


MAGIC = b"QBFXQARCHIVE\x00\x01"
NONCE_SIZE = 12
TAG_SIZE = 16
MAX_MANIFEST_BYTES = 1024 * 1024
_PDF_NAME_RE = re.compile(r"^rx-(\d+)-([0-9a-f]{20})\.pdf$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class FxqArchiveError(Exception):
    """归档操作失败；消息不得包含患者或处方正文。"""


@dataclass(frozen=True)
class StorageEntry:
    name: str
    size: int
    sha256: str


@dataclass(frozen=True)
class StorageReport:
    root: Path
    entries: tuple[StorageEntry, ...]
    errors: tuple[str, ...]

    @property
    def total_bytes(self) -> int:
        return sum(item.size for item in self.entries)


@dataclass(frozen=True)
class ArchiveReport:
    count: int
    total_bytes: int
    created_at: str


def archive_key_bytes(value: str | None = None) -> bytes:
    encoded = (value if value is not None else settings.FXQ_ARCHIVE_KEY).strip()
    if not encoded:
        raise FxqArchiveError("FXQ_ARCHIVE_KEY 未配置")
    try:
        raw = base64.b64decode(encoded.encode("ascii"), altchars=b"-_", validate=True)
    except (ValueError, UnicodeError) as exc:
        raise FxqArchiveError("FXQ_ARCHIVE_KEY 不是有效 urlsafe-base64") from exc
    if len(raw) != 32:
        raise FxqArchiveError("FXQ_ARCHIVE_KEY 解码后必须为 32 字节")
    return raw


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as fp:
        for chunk in iter(lambda: fp.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def scan_storage(root: Path | None = None) -> StorageReport:
    source = root if root is not None else _storage_root()
    errors: list[str] = []
    entries: list[StorageEntry] = []
    if source.is_symlink():
        return StorageReport(source, (), ("存储根目录不得是符号链接",))
    source = source.resolve()
    if not source.exists():
        return StorageReport(source, (), ("存储根目录不存在",))
    if not source.is_dir():
        return StorageReport(source, (), ("存储根路径不是目录",))
    if os.name == "posix" and stat.S_IMODE(source.stat().st_mode) != 0o700:
        errors.append("存储根目录权限必须为 700")

    for path in sorted(source.iterdir(), key=lambda item: item.name):
        if path.is_symlink():
            errors.append("存储目录中存在符号链接")
            continue
        if not path.is_file():
            errors.append("存储目录中存在非普通文件")
            continue
        match = _PDF_NAME_RE.fullmatch(path.name)
        if not match:
            errors.append("存储目录中存在命名不合规文件")
            continue
        if os.name == "posix" and stat.S_IMODE(path.stat().st_mode) != 0o600:
            errors.append("存在权限不是 600 的签后 PDF")
        try:
            with path.open("rb") as fp:
                if fp.read(5) != b"%PDF-":
                    errors.append("存在内容格式不正确的签后 PDF")
                    continue
            digest, size = _sha256_file(path)
        except OSError:
            errors.append("存在无法读取的签后 PDF")
            continue
        if size > settings.FXQ_MAX_PDF_BYTES:
            errors.append("存在超过配置大小限制的签后 PDF")
            continue
        if not digest.startswith(match.group(2)):
            errors.append("存在文件名摘要与内容不一致的签后 PDF")
            continue
        entries.append(StorageEntry(path.name, size, digest))
    return StorageReport(source, tuple(entries), tuple(sorted(set(errors))))


def fix_storage_permissions(root: Path | None = None) -> StorageReport:
    """只修复根目录和已识别 PDF 的 mode，不处理异常文件或符号链接。"""
    source = root if root is not None else _storage_root()
    if source.is_symlink():
        raise FxqArchiveError("拒绝修改符号链接存储目录")
    source.mkdir(parents=True, exist_ok=True, mode=0o700)
    source = source.resolve()
    if os.name == "posix":
        source.chmod(0o700)
        for path in source.iterdir():
            if path.is_file() and not path.is_symlink() and _PDF_NAME_RE.fullmatch(path.name):
                path.chmod(0o600)
    return scan_storage(source)


def storage_write_test(root: Path | None = None) -> None:
    """创建并删除一个 0600 空探针，验证 API 对生产卷确实可写。"""
    source = root if root is not None else _storage_root()
    if source.is_symlink():
        raise FxqArchiveError("存储根目录不得是符号链接")
    source = source.resolve()
    if not source.is_dir():
        raise FxqArchiveError("存储根目录不存在")
    import tempfile

    fd = temp_name = None
    try:
        fd, temp_name = tempfile.mkstemp(prefix=".fxq-write-test.", dir=source)
        os.fchmod(fd, 0o600) if os.name == "posix" else None
        os.close(fd)
        fd = None
    except OSError as exc:
        raise FxqArchiveError("API 对签后处方卷没有写权限") from exc
    finally:
        if fd is not None:
            os.close(fd)
        if temp_name:
            Path(temp_name).unlink(missing_ok=True)


class _EncryptingWriter:
    def __init__(self, raw: BinaryIO, key: bytes):
        self.raw = raw
        self.nonce = os.urandom(NONCE_SIZE)
        self.raw.write(MAGIC)
        self.raw.write(self.nonce)
        self._encryptor = Cipher(algorithms.AES(key), modes.GCM(self.nonce)).encryptor()
        self._encryptor.authenticate_additional_data(MAGIC + self.nonce)
        self._position = 0
        self._finalized = False

    def write(self, data: bytes) -> int:
        if self._finalized:
            raise ValueError("archive writer finalized")
        encrypted = self._encryptor.update(data)
        if encrypted:
            self.raw.write(encrypted)
        self._position += len(data)
        return len(data)

    def tell(self) -> int:
        return self._position

    def flush(self) -> None:
        self.raw.flush()

    def finalize(self) -> None:
        if self._finalized:
            return
        tail = self._encryptor.finalize()
        if tail:
            self.raw.write(tail)
        self.raw.write(self._encryptor.tag)
        self._finalized = True


class _DecryptingReader(io.RawIOBase):
    def __init__(self, raw: BinaryIO, key: bytes):
        self._raw = raw
        self._raw.seek(0, os.SEEK_END)
        total_size = self._raw.tell()
        header_size = len(MAGIC) + NONCE_SIZE
        if total_size <= header_size + TAG_SIZE:
            raise FxqArchiveError("归档文件长度不正确")
        self._raw.seek(0)
        magic = self._raw.read(len(MAGIC))
        nonce = self._raw.read(NONCE_SIZE)
        if magic != MAGIC or len(nonce) != NONCE_SIZE:
            raise FxqArchiveError("归档版本头不正确")
        self._raw.seek(-TAG_SIZE, os.SEEK_END)
        tag = self._raw.read(TAG_SIZE)
        self._remaining = total_size - header_size - TAG_SIZE
        self._raw.seek(header_size)
        self._decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
        self._decryptor.authenticate_additional_data(MAGIC + nonce)
        self._plain_position = 0
        self._finalized = False

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self._plain_position

    def _finalize(self) -> bytes:
        if self._finalized:
            return b""
        try:
            tail = self._decryptor.finalize()
        except InvalidTag as exc:
            raise FxqArchiveError("归档认证失败，文件已损坏或密钥不正确") from exc
        self._finalized = True
        return tail

    def read(self, size: int = -1) -> bytes:
        if self._finalized:
            return b""
        if size is None or size < 0:
            chunks: list[bytes] = []
            while self._remaining:
                chunks.append(self.read(min(1024 * 1024, self._remaining)))
            chunks.append(self._finalize())
            return b"".join(chunks)
        if size == 0:
            return b""
        if not self._remaining:
            return self._finalize()
        amount = min(size, self._remaining)
        chunk = self._raw.read(amount)
        if len(chunk) != amount:
            raise FxqArchiveError("归档密文被截断")
        self._remaining -= amount
        plain = self._decryptor.update(chunk)
        self._plain_position += len(plain)
        if not self._remaining:
            tail = self._finalize()
            self._plain_position += len(tail)
            plain += tail
        return plain


def _manifest_bytes(report: StorageReport) -> bytes:
    payload = {
        "version": 1,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "files": [
            {"name": item.name, "size": item.size, "sha256": item.sha256}
            for item in report.entries
        ],
    }
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _safe_tar_info(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mode = 0o600
    return info


def create_encrypted_backup(
    output: Path,
    *,
    root: Path | None = None,
    key_value: str | None = None,
) -> ArchiveReport:
    key = archive_key_bytes(key_value)
    report = scan_storage(root)
    if report.errors:
        raise FxqArchiveError("存储预检未通过：" + "；".join(report.errors))
    if not output.is_absolute():
        raise FxqArchiveError("归档输出必须使用绝对路径")
    if not output.parent.is_dir():
        raise FxqArchiveError("归档输出目录不存在")
    if output.exists():
        raise FxqArchiveError("拒绝覆盖已有归档文件")
    if os.name == "posix" and stat.S_IMODE(output.parent.stat().st_mode) & 0o077:
        raise FxqArchiveError("归档输出目录权限过宽，必须为 700")

    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as raw:
            writer = _EncryptingWriter(raw, key)
            with tarfile.open(fileobj=writer, mode="w|gz", format=tarfile.PAX_FORMAT) as archive:
                manifest = _manifest_bytes(report)
                manifest_info = tarfile.TarInfo("manifest.json")
                manifest_info.size = len(manifest)
                manifest_info.mode = 0o600
                archive.addfile(manifest_info, io.BytesIO(manifest))
                for entry in report.entries:
                    archive.add(
                        report.root / entry.name,
                        arcname=f"prescriptions/{entry.name}",
                        recursive=False,
                        filter=_safe_tar_info,
                    )
            writer.finalize()
            raw.flush()
            os.fsync(raw.fileno())
        if os.name == "posix":
            output.chmod(0o600)
        verified = verify_encrypted_backup(output, key_value=key_value)
        if verified.count != len(report.entries) or verified.total_bytes != report.total_bytes:
            raise FxqArchiveError("归档回读结果与源文件不一致")
        return verified
    except Exception:
        output.unlink(missing_ok=True)
        raise


def _load_manifest(source: BinaryIO, size: int) -> tuple[dict, dict[str, dict]]:
    if size <= 0 or size > MAX_MANIFEST_BYTES:
        raise FxqArchiveError("归档清单大小不正确")
    try:
        payload = json.loads(source.read().decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise FxqArchiveError("归档清单格式不正确") from exc
    if payload.get("version") != 1 or not isinstance(payload.get("files"), list):
        raise FxqArchiveError("归档清单版本或文件列表不正确")
    expected: dict[str, dict] = {}
    for item in payload["files"]:
        if not isinstance(item, dict):
            raise FxqArchiveError("归档清单条目不正确")
        name, digest, item_size = item.get("name"), item.get("sha256"), item.get("size")
        if (
            not isinstance(name, str)
            or not _PDF_NAME_RE.fullmatch(name)
            or not isinstance(digest, str)
            or not _SHA256_RE.fullmatch(digest)
            or not isinstance(item_size, int)
            or item_size < 0
            or item_size > settings.FXQ_MAX_PDF_BYTES
            or name in expected
        ):
            raise FxqArchiveError("归档清单含不合规条目")
        expected[name] = item
    return payload, expected


def _consume_archive(
    archive_path: Path,
    *,
    key_value: str | None,
    restore_target: Path | None,
) -> ArchiveReport:
    key = archive_key_bytes(key_value)
    if not archive_path.is_file():
        raise FxqArchiveError("归档文件不存在")
    created: list[Path] = []
    if restore_target is not None:
        if restore_target.is_symlink() or not restore_target.is_dir():
            raise FxqArchiveError("恢复演练目标必须是已存在的普通目录")
        if any(restore_target.iterdir()):
            raise FxqArchiveError("恢复演练目标目录必须为空")
        restore_target = restore_target.resolve()
        if os.name == "posix":
            restore_target.chmod(0o700)

    try:
        with archive_path.open("rb") as raw:
            reader = _DecryptingReader(raw, key)
            payload = expected = None
            seen: set[str] = set()
            total_bytes = 0
            with tarfile.open(fileobj=reader, mode="r|gz") as archive:
                for index, member in enumerate(archive):
                    if index == 0:
                        if member.name != "manifest.json" or not member.isfile():
                            raise FxqArchiveError("归档首项不是清单")
                        source = archive.extractfile(member)
                        if source is None:
                            raise FxqArchiveError("无法读取归档清单")
                        payload, expected = _load_manifest(source, member.size)
                        continue
                    if payload is None or expected is None:
                        raise FxqArchiveError("归档缺少清单")
                    if not member.isfile() or not member.name.startswith("prescriptions/"):
                        raise FxqArchiveError("归档含不允许的成员")
                    name = member.name.removeprefix("prescriptions/")
                    if "/" in name or name not in expected or name in seen:
                        raise FxqArchiveError("归档成员名称或对应关系不正确")
                    if member.size != expected[name]["size"]:
                        raise FxqArchiveError("归档 PDF 声明大小与清单不一致")
                    source = archive.extractfile(member)
                    if source is None:
                        raise FxqArchiveError("无法读取归档 PDF")
                    digest = hashlib.sha256()
                    size = 0
                    first = True
                    target_fp = None
                    try:
                        if restore_target is not None:
                            target = restore_target / name
                            target_fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                            target_fp = os.fdopen(target_fd, "wb")
                            created.append(target)
                        for chunk in iter(lambda: source.read(1024 * 1024), b""):
                            if first and not chunk.startswith(b"%PDF-"):
                                raise FxqArchiveError("归档中存在非 PDF 内容")
                            first = False
                            digest.update(chunk)
                            size += len(chunk)
                            if target_fp is not None:
                                target_fp.write(chunk)
                        if target_fp is not None:
                            target_fp.flush()
                            os.fsync(target_fp.fileno())
                    finally:
                        if target_fp is not None:
                            target_fp.close()
                    item = expected[name]
                    if size != item["size"] or digest.hexdigest() != item["sha256"]:
                        raise FxqArchiveError("归档 PDF 摘要或大小校验失败")
                    seen.add(name)
                    total_bytes += size
            while reader.read(1024 * 1024):
                pass
            if payload is None or expected is None:
                raise FxqArchiveError("归档缺少清单")
            if seen != set(expected):
                raise FxqArchiveError("归档文件与清单数量不一致")
            return ArchiveReport(len(seen), total_bytes, str(payload.get("createdAt") or ""))
    except Exception:
        for path in created:
            path.unlink(missing_ok=True)
        raise


def verify_encrypted_backup(archive_path: Path, *, key_value: str | None = None) -> ArchiveReport:
    return _consume_archive(archive_path, key_value=key_value, restore_target=None)


def restore_test_encrypted_backup(
    archive_path: Path,
    target: Path,
    *,
    key_value: str | None = None,
) -> ArchiveReport:
    return _consume_archive(archive_path, key_value=key_value, restore_target=target)
