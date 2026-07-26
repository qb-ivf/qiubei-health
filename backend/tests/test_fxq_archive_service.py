"""Tests for private signed-PDF storage and encrypted recovery archives."""
from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from app.services.fxq_archive_service import (
    MAGIC,
    FxqArchiveError,
    create_encrypted_backup,
    fix_storage_permissions,
    restore_test_encrypted_backup,
    scan_storage,
    verify_encrypted_backup,
)


def _key() -> str:
    return Fernet.generate_key().decode("ascii")


def _write_signed_pdf(root: Path, prescription_id: int, content: bytes) -> Path:
    digest = hashlib.sha256(content).hexdigest()
    path = root / f"rx-{prescription_id}-{digest[:20]}.pdf"
    path.write_bytes(content)
    if os.name == "posix":
        path.chmod(0o600)
    return path


def _private_dir(path: Path) -> Path:
    path.mkdir(mode=0o700)
    if os.name == "posix":
        path.chmod(0o700)
    return path


def test_scan_storage_checks_digest_and_permissions(tmp_path):
    root = _private_dir(tmp_path / "signed")
    content = b"%PDF-1.7\nsynthetic signed prescription"
    pdf = _write_signed_pdf(root, 12, content)

    report = scan_storage(root)

    assert report.errors == ()
    assert report.total_bytes == len(content)
    assert report.entries[0].name == pdf.name
    assert report.entries[0].sha256 == hashlib.sha256(content).hexdigest()


def test_fix_storage_permissions(tmp_path):
    root = _private_dir(tmp_path / "signed")
    pdf = _write_signed_pdf(root, 3, b"%PDF-1.7\nprivate")
    if os.name == "posix":
        root.chmod(0o755)
        pdf.chmod(0o644)

    report = fix_storage_permissions(root)

    assert report.errors == ()
    if os.name == "posix":
        assert stat.S_IMODE(root.stat().st_mode) == 0o700
        assert stat.S_IMODE(pdf.stat().st_mode) == 0o600


def test_encrypted_backup_verify_and_restore_round_trip(tmp_path):
    root = _private_dir(tmp_path / "signed")
    first = _write_signed_pdf(root, 7, b"%PDF-1.7\nfirst synthetic prescription")
    second = _write_signed_pdf(root, 8, b"%PDF-1.7\nsecond synthetic prescription")
    backup_dir = _private_dir(tmp_path / "backup")
    archive = backup_dir / "prescriptions.qba"
    key = _key()

    created = create_encrypted_backup(archive, root=root, key_value=key)
    verified = verify_encrypted_backup(archive, key_value=key)
    restore = _private_dir(tmp_path / "restore")
    restored = restore_test_encrypted_backup(archive, restore, key_value=key)

    assert created.count == verified.count == restored.count == 2
    assert created.total_bytes == first.stat().st_size + second.stat().st_size
    assert archive.read_bytes().startswith(MAGIC)
    assert first.read_bytes() not in archive.read_bytes()
    assert (restore / first.name).read_bytes() == first.read_bytes()
    assert (restore / second.name).read_bytes() == second.read_bytes()
    if os.name == "posix":
        assert stat.S_IMODE(archive.stat().st_mode) == 0o600
        assert stat.S_IMODE((restore / first.name).stat().st_mode) == 0o600


def test_backup_rejects_overwrite_and_nonempty_restore_target(tmp_path):
    root = _private_dir(tmp_path / "signed")
    _write_signed_pdf(root, 9, b"%PDF-1.7\nsynthetic")
    backup_dir = _private_dir(tmp_path / "backup")
    archive = backup_dir / "prescriptions.qba"
    key = _key()
    create_encrypted_backup(archive, root=root, key_value=key)

    with pytest.raises(FxqArchiveError, match="覆盖"):
        create_encrypted_backup(archive, root=root, key_value=key)

    restore = _private_dir(tmp_path / "restore")
    (restore / "keep.txt").write_text("do not overwrite", encoding="utf-8")
    with pytest.raises(FxqArchiveError, match="空"):
        restore_test_encrypted_backup(archive, restore, key_value=key)


def test_wrong_key_and_tampering_fail_authentication(tmp_path):
    root = _private_dir(tmp_path / "signed")
    _write_signed_pdf(root, 10, b"%PDF-1.7\nsynthetic")
    backup_dir = _private_dir(tmp_path / "backup")
    archive = backup_dir / "prescriptions.qba"
    key = _key()
    create_encrypted_backup(archive, root=root, key_value=key)

    with pytest.raises(FxqArchiveError, match="认证失败"):
        verify_encrypted_backup(archive, key_value=_key())

    tampered = bytearray(archive.read_bytes())
    tampered[len(tampered) // 2] ^= 0x01
    archive.write_bytes(tampered)
    with pytest.raises((FxqArchiveError, OSError)):
        verify_encrypted_backup(archive, key_value=key)


def test_scan_rejects_digest_name_mismatch(tmp_path):
    root = _private_dir(tmp_path / "signed")
    pdf = root / "rx-11-00000000000000000000.pdf"
    pdf.write_bytes(b"%PDF-1.7\nsynthetic")
    if os.name == "posix":
        pdf.chmod(0o600)

    report = scan_storage(root)

    assert report.entries == ()
    assert any("摘要" in message for message in report.errors)
