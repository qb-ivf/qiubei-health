"""放心签处方签后验签与受保护存储测试。"""
import hashlib
import os
import stat
from types import SimpleNamespace

import pytest

from app.core.config import settings
from app.services import fxq_document_service
from app.services.fxq_ca import FxqCaError
from app.services.fxq_document_service import (
    FxqDocumentError,
    _validate_verification,
    load_signed_pdf,
    store_signed_pdf,
)


def _signature(name: str) -> dict:
    return {
        "signerName": name,
        "issuingAuthority": "测试CA",
        "dateTime": "202607241030",
        "timeValidity": True,
        "isVerify": True,
        "idNo": "不得落库",
        "sealDate": "不得落库",
        "signatureDegist": "不得落库",
        "certFormat": "X.509",
        "certSerialNumber": f"serial-{name}",
        "notBefore": "2000-01-01 00:00:00",
        "notAfter": "2100-01-01 00:00:00",
        "signatureEncryptionAlgorithm": "RSA",
        "signatureHashAlgorithm": "SHA256",
    }


def test_verification_requires_all_three_valid_signatures_and_strips_sensitive_fields():
    pdf = b"%PDF-1.7\nsigned prescription"
    digest = hashlib.sha256(pdf).hexdigest()
    names = ["医师甲", "药师乙", "测试医院有限公司"]
    data = {
        "pdfModify": True,
        "signatureList": [_signature(name) for name in names],
        "fileDegist": digest,
    }

    file_digest, count, _, report = _validate_verification(
        data, expected_names=names, signed_pdf=pdf
    )

    assert file_digest == digest
    assert count == 3
    assert [item["signerName"] for item in report] == names
    assert all("idNo" not in item for item in report)
    assert all("sealDate" not in item for item in report)
    assert all("signatureDegist" not in item for item in report)


def test_verification_rejects_digest_mismatch():
    pdf = b"%PDF-1.7\nsigned prescription"
    names = ["医师甲", "药师乙", "测试医院有限公司"]
    with pytest.raises(FxqDocumentError, match="摘要"):
        _validate_verification(
            {
                "pdfModify": True,
                "signatureList": [_signature(name) for name in names],
                "fileDegist": "0" * 64,
            },
            expected_names=names,
            signed_pdf=pdf,
        )


def test_verification_accepts_ca_subject_wrapping_the_expected_name():
    pdf = b"%PDF-1.7\nsigned prescription"
    names = ["医师甲", "药师乙", "测试医院有限公司"]
    signatures = [_signature(name) for name in names]
    signatures[0]["signerName"] = "CN=医师甲,OU=Digital Certificate"
    _validate_verification(
        {
            "pdfModify": True,
            "signatureList": signatures,
            "fileDegist": hashlib.sha256(pdf).hexdigest(),
        },
        expected_names=names,
        signed_pdf=pdf,
    )


def test_signed_pdf_storage_is_private_and_digest_named(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "FXQ_SIGNED_PDF_DIR", str(tmp_path))
    pdf = b"%PDF-1.7\nsigned prescription"
    digest = hashlib.sha256(pdf).hexdigest()

    reference = store_signed_pdf(12, pdf, digest)

    assert reference == f"rx-12-{digest[:20]}.pdf"
    assert load_signed_pdf(reference) == pdf
    if os.name == "posix":
        assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o700
        assert stat.S_IMODE((tmp_path / reference).stat().st_mode) == 0o600
    with pytest.raises(FxqDocumentError):
        load_signed_pdf("../outside.pdf")


@pytest.mark.asyncio
async def test_provider_timeout_stops_document_signing(monkeypatch):
    async def timeout(*, name: str):
        raise FxqCaError("放心签网络暂时不可用", retryable=True)

    monkeypatch.setattr(settings, "FXQ_DOCUMENT_SIGN_ENABLED", True)
    monkeypatch.setattr(settings, "FXQ_COMPANY_NAME", "测试医院有限公司")
    monkeypatch.setattr(settings, "FXQ_COMPANY_IDNO", "91120116MACJA9PX45")
    monkeypatch.setattr(
        fxq_document_service.fxq_ca_client,
        "generate_personal_seal",
        timeout,
    )

    with pytest.raises(FxqDocumentError, match="放心签网络暂时不可用") as captured:
        await fxq_document_service.sign_prescription_pdf(
            b"%PDF-1.7\nsynthetic prescription",
            doctor_name="医师甲",
            doctor_id_no="120101199001011234",
            pharmacist_name="药师乙",
            pharmacist_id_no="120101199001015678",
        )

    assert captured.value.retryable is True
    assert captured.value.manual_review is True


@pytest.mark.asyncio
async def test_medical_record_signing_has_doctor_and_hospital_only(monkeypatch):
    signed_pdf = b"%PDF-1.7\nsigned medical record"
    captured = {}

    async def personal(*, name: str):
        return SimpleNamespace(data=f"seal-{name}")

    async def company(*, name: str):
        return SimpleNamespace(data=f"seal-{name}")

    async def sign_pdf(*, contract_base64: str, signers: list):
        captured["signers"] = signers
        assert contract_base64
        return SimpleNamespace(data="https://openapi.fangxinqian.cn/signed.pdf", trade_no="SIGN-1")

    async def verify_pdf(*, file_url: str):
        assert file_url.endswith("signed.pdf")
        names = ["医师甲", "测试医院有限公司"]
        return SimpleNamespace(
            data={
                "pdfModify": True,
                "signatureList": [_signature(name) for name in names],
                "fileDegist": hashlib.sha256(signed_pdf).hexdigest(),
            },
            trade_no="VERIFY-1",
        )

    async def download_pdf(*, file_url: str):
        assert file_url.endswith("signed.pdf")
        return signed_pdf

    monkeypatch.setattr(settings, "FXQ_DOCUMENT_SIGN_ENABLED", True)
    monkeypatch.setattr(settings, "FXQ_COMPANY_NAME", "测试医院有限公司")
    monkeypatch.setattr(settings, "FXQ_COMPANY_IDNO", "91120116MACJA9PX45")
    monkeypatch.setattr(fxq_document_service.fxq_ca_client, "generate_personal_seal", personal)
    monkeypatch.setattr(fxq_document_service.fxq_ca_client, "generate_company_seal", company)
    monkeypatch.setattr(fxq_document_service.fxq_ca_client, "sign_pdf", sign_pdf)
    monkeypatch.setattr(fxq_document_service.fxq_ca_client, "verify_pdf", verify_pdf)
    monkeypatch.setattr(fxq_document_service.fxq_ca_client, "download_pdf", download_pdf)

    result = await fxq_document_service.sign_medical_record_pdf(
        b"%PDF-1.7\nmedical record",
        doctor_name="医师甲",
        doctor_id_no="120101199001011234",
    )

    assert [signer["name"] for signer in captured["signers"]] == [
        "医师甲",
        "测试医院有限公司",
    ]
    assert result.signature_count == 2
    assert len(result.verify_report) == 2
