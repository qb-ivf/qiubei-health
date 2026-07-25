"""放心签电子处方 PDF 三方签署、验签和受保护文件存储。

签署顺序在一个标准 API 请求中完成：开方医师、审核药师、医院企业。
身份证仅作为调用参数在内存中短暂存在；验签报告会主动剔除证件号、印章数据和签名值。
"""
from __future__ import annotations

import base64
import hashlib
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..core.config import settings
from .fxq_ca import FxqCaError, fxq_ca_client


class FxqDocumentError(Exception):
    """签署或验签不满足处方生效条件。"""


@dataclass(frozen=True)
class DocumentSignResult:
    signed_pdf: bytes
    sign_trade_no: str
    verify_trade_no: str | None
    source_digest: str
    file_digest: str
    signature_count: int
    signed_at: datetime
    verify_report: list[dict[str, Any]]


def _truthy(value: Any) -> bool:
    return value is True or value == 1 or (isinstance(value, str) and value.lower() == "true")


def _parse_provider_time(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y%m%d%H%M%S", "%Y%m%d%H%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _matches_subject(item: dict[str, Any], expected_name: str) -> bool:
    """不同 CA 可能把主体包装成证书 DN/签名原因，允许全称作为其中的完整片段。"""
    for field in ("signerName", "signatureUserName", "signatureCertificate", "signatureReason"):
        value = str(item.get(field) or "").strip()
        if value == expected_name or expected_name in value:
            return True
    return False


def _validate_verification(
    data: dict[str, Any],
    *,
    expected_names: list[str],
    signed_pdf: bytes,
) -> tuple[str, int, datetime, list[dict[str, Any]]]:
    if not _truthy(data.get("pdfModify")):
        raise FxqDocumentError("放心签验签判定文件已被篡改")

    signatures = data.get("signatureList")
    if not isinstance(signatures, list):
        raise FxqDocumentError("放心签验签结果缺少签名列表")
    if len(signatures) < len(expected_names):
        raise FxqDocumentError(
            f"放心签验签签名数量不足：期望 {len(expected_names)}，实际 {len(signatures)}"
        )

    remaining = [item for item in signatures if isinstance(item, dict)]
    normalized: list[dict[str, Any]] = []
    signed_times: list[datetime] = []
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for expected_name in expected_names:
        matched = next(
            (
                item
                for item in remaining
                if _matches_subject(item, expected_name)
            ),
            None,
        )
        if matched is None:
            raise FxqDocumentError(f"放心签验签缺少签署主体：{expected_name}")
        remaining.remove(matched)
        if not _truthy(matched.get("isVerify")):
            raise FxqDocumentError(f"放心签验签判定“{expected_name}”签名无效")
        if not _truthy(matched.get("timeValidity")):
            raise FxqDocumentError(f"放心签验签判定“{expected_name}”时间戳无效")

        not_before = _parse_provider_time(matched.get("notBefore"))
        not_after = _parse_provider_time(matched.get("notAfter"))
        if not_before and now < not_before:
            raise FxqDocumentError(f"“{expected_name}”签名证书尚未生效")
        if not_after and now > not_after:
            raise FxqDocumentError(f"“{expected_name}”签名证书已过期")
        signed_time = _parse_provider_time(matched.get("dateTime") or matched.get("timeStr"))
        if signed_time:
            signed_times.append(signed_time)

        normalized.append(
            {
                "signerName": expected_name,
                "issuingAuthority": str(matched.get("issuingAuthority") or "")[:128] or None,
                "dateTime": str(matched.get("dateTime") or "")[:32] or None,
                "timeAuthority": str(matched.get("timeAuthority") or "")[:128] or None,
                "timeValidity": True,
                "isVerify": True,
                "certFormat": str(matched.get("certFormat") or "")[:32] or None,
                "certSerialNumber": str(matched.get("certSerialNumber") or "")[:128] or None,
                "notBefore": str(matched.get("notBefore") or "")[:32] or None,
                "notAfter": str(matched.get("notAfter") or "")[:32] or None,
                "signatureEncryptionAlgorithm": str(
                    matched.get("signatureEncryptionAlgorithm") or ""
                )[:32]
                or None,
                "signatureHashAlgorithm": str(matched.get("signatureHashAlgorithm") or "")[:32]
                or None,
            }
        )

    local_digest = hashlib.sha256(signed_pdf).hexdigest()
    provider_digest = str(data.get("fileDegist") or "").lower()
    if provider_digest and provider_digest != local_digest:
        raise FxqDocumentError("放心签验签摘要与下载的签后 PDF 不一致")
    return (
        provider_digest or local_digest,
        len(signatures),
        max(signed_times) if signed_times else now,
        normalized,
    )


async def sign_prescription_pdf(
    pdf_bytes: bytes,
    *,
    doctor_name: str,
    doctor_id_no: str,
    pharmacist_name: str,
    pharmacist_id_no: str,
) -> DocumentSignResult:
    """生成三方印章、签署处方、验签并下载签后原件。"""
    if not settings.FXQ_DOCUMENT_SIGN_ENABLED:
        raise FxqDocumentError("FXQ_DOCUMENT_SIGN_ENABLED 未开启")
    if not pdf_bytes.startswith(b"%PDF-"):
        raise FxqDocumentError("待签署文件不是有效 PDF")
    if len(pdf_bytes) > settings.FXQ_MAX_PDF_BYTES:
        raise FxqDocumentError("待签署 PDF 超过大小限制")
    company_name = settings.FXQ_COMPANY_NAME.strip()
    company_id_no = settings.FXQ_COMPANY_IDNO.strip()
    if not company_name or not company_id_no:
        raise FxqDocumentError("医院签章主体名称或统一社会信用代码未配置")

    try:
        doctor_seal = await fxq_ca_client.generate_personal_seal(name=doctor_name)
        pharmacist_seal = await fxq_ca_client.generate_personal_seal(name=pharmacist_name)
        company_seal = await fxq_ca_client.generate_company_seal(name=company_name)
        sign_result = await fxq_ca_client.sign_pdf(
            contract_base64=base64.b64encode(pdf_bytes).decode("ascii"),
            signers=[
                {
                    "name": doctor_name,
                    "idno": doctor_id_no,
                    "seal": doctor_seal.data,
                    "size": 82,
                    "areas": [{"x": 78, "y": 76, "page": 1}],
                },
                {
                    "name": pharmacist_name,
                    "idno": pharmacist_id_no,
                    "seal": pharmacist_seal.data,
                    "size": 82,
                    "areas": [{"x": 245, "y": 76, "page": 1}],
                },
                {
                    "name": company_name,
                    "idno": company_id_no,
                    "seal": company_seal.data,
                    "size": 100,
                    "areas": [{"x": 420, "y": 66, "page": 1}],
                },
            ],
        )
        verify_result = await fxq_ca_client.verify_pdf(file_url=sign_result.data)
        signed_pdf = await fxq_ca_client.download_pdf(file_url=sign_result.data)
    except FxqCaError as exc:
        raise FxqDocumentError(str(exc)) from exc

    file_digest, signature_count, signed_at, report = _validate_verification(
        verify_result.data,
        expected_names=[doctor_name, pharmacist_name, company_name],
        signed_pdf=signed_pdf,
    )
    if not sign_result.trade_no:
        raise FxqDocumentError("放心签签署响应缺少交易流水")
    return DocumentSignResult(
        signed_pdf=signed_pdf,
        sign_trade_no=sign_result.trade_no,
        verify_trade_no=verify_result.trade_no,
        source_digest=hashlib.sha256(pdf_bytes).hexdigest(),
        file_digest=file_digest,
        signature_count=signature_count,
        signed_at=signed_at,
        verify_report=report,
    )


def _storage_root() -> Path:
    configured = settings.FXQ_SIGNED_PDF_DIR.strip()
    root = Path(configured) if configured else Path(__file__).resolve().parents[2] / "storage" / "prescriptions"
    return root.resolve()


def store_signed_pdf(rx_id: int, data: bytes, digest: str) -> str:
    """原子保存签后 PDF，返回数据库可存的相对文件名。"""
    if not data.startswith(b"%PDF-"):
        raise FxqDocumentError("拒绝保存非 PDF 签后文件")
    root = _storage_root()
    root.mkdir(parents=True, exist_ok=True)
    filename = f"rx-{int(rx_id)}-{digest[:20]}.pdf"
    target = (root / filename).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise FxqDocumentError("签后 PDF 存储路径越界") from exc

    fd, temp_name = tempfile.mkstemp(prefix=f".{filename}.", suffix=".tmp", dir=root)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise
    return filename


def load_signed_pdf(reference: str) -> bytes:
    """只从受保护目录读取数据库记录指向的单个 PDF 文件。"""
    ref = Path(reference)
    if ref.is_absolute() or len(ref.parts) != 1 or ref.suffix.lower() != ".pdf":
        raise FxqDocumentError("签后 PDF 引用格式不正确")
    root = _storage_root()
    target = (root / ref).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise FxqDocumentError("签后 PDF 读取路径越界") from exc
    try:
        data = target.read_bytes()
    except FileNotFoundError as exc:
        raise FxqDocumentError("签后 PDF 文件不存在，请联系管理员恢复归档") from exc
    if not data.startswith(b"%PDF-"):
        raise FxqDocumentError("签后 PDF 归档文件格式不正确")
    return data
