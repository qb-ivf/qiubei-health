"""放心签处方签后验签与受保护存储测试。"""
import hashlib
import os
import stat

import pytest

from app.core.config import settings
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
