from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.services import compliance_service


def _report():
    return SimpleNamespace(
        method="uploadDrugCatalogue", payload=[{"x": 1}], status="pending",
        msg_code=None, latency_ms=0, resp_msg=None, last_error=None,
        retries=0, next_retry_at=None,
    )


def _prescription():
    return SimpleNamespace(
        recipe_unique_id="RX-001",
        diagnosis="测试诊断",
        items=[{"name": "测试药品", "qty": 1, "usage": "口服"}],
        checked_at=None,
    )


def test_prescription_source_pdf_is_byte_stable():
    rx = _prescription()
    first = compliance_service.generate_prescription_pdf(
        rx, "测试患者", "测试医生", "测试药师", for_signing=True
    )
    second = compliance_service.generate_prescription_pdf(
        rx, "测试患者", "测试医生", "测试药师", for_signing=True
    )
    assert first == second
    assert first.startswith(b"%PDF-")


@pytest.mark.asyncio
async def test_disabled_production_keeps_report_pending(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", False)
    monkeypatch.setattr(settings, "TJ_REPORT_ENABLED", False)
    report = _report()
    await compliance_service._send_one(report)
    assert report.status == "pending"
    assert "保持待发送" in report.last_error


@pytest.mark.asyncio
async def test_disabled_debug_mode_still_simulates(monkeypatch):
    monkeypatch.setattr(settings, "DEBUG", True)
    monkeypatch.setattr(settings, "TJ_REPORT_ENABLED", False)
    report = _report()
    await compliance_service._send_one(report)
    assert report.status == "success"
    assert report.msg_code == 200
    assert "本地模拟成功" in report.resp_msg
