"""CA 管理员进度聚合必须只输出必要的非敏感字段。"""
from datetime import datetime
from types import SimpleNamespace

from app.services.ca_service import _progress_counts, _subject_snapshot


def test_admin_subject_snapshot_uses_explicit_safe_field_allowlist():
    enrollment = SimpleNamespace(
        status="succeeded",
        face_code="0",
        completed_at=datetime(2026, 7, 27, 1, 2, 3),
        last_checked_at=datetime(2026, 7, 27, 1, 2, 4),
        verify_id="不得返回",
        order_no="不得返回",
        agreement_url_enc="不得返回",
        similarity="不得返回",
    )

    row = _subject_snapshot(
        subject_type="doctor",
        subject_id=7,
        name="医师甲",
        account_status="approved",
        record_ready=True,
        enrollment=enrollment,
    )

    assert row["ca_status"] == "succeeded"
    assert row["face_code"] == "0"
    assert set(row) == {
        "subject_type",
        "subject_id",
        "name",
        "account_status",
        "record_ready",
        "ca_status",
        "face_code",
        "completed_at",
        "last_checked_at",
    }
    assert "verify_id" not in row
    assert "order_no" not in row
    assert "agreement_url_enc" not in row
    assert "similarity" not in row


def test_admin_progress_counts_each_local_state():
    rows = [
        {"record_ready": True, "ca_status": "succeeded"},
        {"record_ready": True, "ca_status": "pending"},
        {"record_ready": False, "ca_status": "failed"},
        {"record_ready": True, "ca_status": "expired"},
        {"record_ready": False, "ca_status": "not_started"},
    ]

    counts = _progress_counts(rows)

    assert counts == {
        "total": 5,
        "record_ready": 3,
        "succeeded": 1,
        "pending": 1,
        "failed": 1,
        "expired": 1,
        "not_started": 1,
    }
