"""放心签高级证书协议/智能双录 API。"""
from html import escape

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...core.database import get_db
from ...models.ca_enrollment import CaEnrollment
from ...schemas.ca import (
    CaAdminOverviewOut,
    CaConfigOut,
    CaEnrollmentOut,
    CaEnrollmentStartOut,
)
from ...services import ca_service
from ...services.fxq_ca import FxqCaError, config_errors, expiry_status
from ..deps import get_current_user, require_role

router = APIRouter(prefix="/ca", tags=["ca"])


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ca_service.CaEnrollmentError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, FxqCaError):
        return HTTPException(status_code=503 if exc.retryable else 502, detail=str(exc))
    return HTTPException(status_code=500, detail="CA 服务处理失败")


@router.get("/config", response_model=CaConfigOut)
async def config(user=Depends(get_current_user)):
    errors = config_errors(settings)
    expiry = expiry_status(settings)
    return CaConfigOut(
        enabled=settings.FXQ_CA_ENABLED,
        document_sign_enabled=settings.FXQ_DOCUMENT_SIGN_ENABLED,
        required=settings.FXQ_CA_REQUIRED,
        ready=not errors and settings.FXQ_CA_ENABLED,
        errors=errors,
        service_expires_on=expiry.service_expires_on,
        personal_cert_expires_on=expiry.personal_cert_expires_on,
        effective_expires_on=expiry.effective_expires_on,
        days_until_expiry=expiry.days_until_expiry,
        expiry_warning=expiry.warning,
        expiry_expired=expiry.expired,
    )


@router.get("/admin/overview", response_model=CaAdminOverviewOut)
async def admin_overview(
    user=Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    """管理员只读查看人员备案/双录进度；不返回身份证、核验 ID、照片或视频。"""
    data = await ca_service.admin_overview(db)
    expiry = expiry_status(settings)
    return CaAdminOverviewOut(
        **data,
        effective_expires_on=expiry.effective_expires_on,
        expiry_warning=expiry.warning,
        expiry_expired=expiry.expired,
        generated_at=ca_service._utcnow(),
    )


@router.get("/enrollments/latest", response_model=CaEnrollmentOut | None)
async def latest(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        return await ca_service.latest_for_user(db, user)
    except (ca_service.CaEnrollmentError, FxqCaError) as exc:
        raise _http_error(exc) from exc


@router.post("/enrollments", response_model=CaEnrollmentStartOut)
async def start(user=Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        enrollment, agreement_url = await ca_service.start_enrollment(db, user)
        await db.commit()
        await db.refresh(enrollment)
    except (ca_service.CaEnrollmentError, FxqCaError) as exc:
        await db.rollback()
        raise _http_error(exc) from exc
    out = CaEnrollmentStartOut.model_validate(enrollment)
    out.agreement_url = agreement_url
    return out


@router.post("/enrollments/{order_no}/refresh", response_model=CaEnrollmentOut)
async def refresh(
    order_no: str, user=Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    try:
        enrollment = await ca_service.enrollment_for_user(db, order_no, user)
        await ca_service.refresh_enrollment(enrollment)
        await db.commit()
        await db.refresh(enrollment)
        return enrollment
    except (ca_service.CaEnrollmentError, FxqCaError) as exc:
        await db.rollback()
        raise _http_error(exc) from exc


def _callback_html(title: str, detail: str) -> HTMLResponse:
    body = (
        "<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{escape(title)}</title></head>"
        "<body style='font-family:system-ui;padding:48px 24px;text-align:center'>"
        f"<h2>{escape(title)}</h2><p>{escape(detail)}</p>"
        "<p>请返回逑贝医生端或运营后台查看最终核验结果。</p></body></html>"
    )
    return HTMLResponse(
        body,
        headers={
            "Cache-Control": "no-store",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'",
            "Referrer-Policy": "no-referrer",
        },
    )


@router.get("/callback", response_class=HTMLResponse)
async def callback(
    order_no: str = Query(alias="orderNo"),
    verify_id: str = Query(default="", alias="verifyId"),
    code: str = Query(default=""),
    db: AsyncSession = Depends(get_db),
):
    """放心签 H5 回跳。回跳参数不作为成功依据，必须服务端再次查询结果。"""
    res = await db.execute(select(CaEnrollment).where(CaEnrollment.order_no == order_no))
    enrollment = res.scalar_one_or_none()
    if not enrollment or (verify_id and enrollment.verify_id and verify_id != enrollment.verify_id):
        return _callback_html("核验链接无效", "未找到匹配的 CA 双录记录。")
    if code != "0":
        enrollment.status = "failed"
        enrollment.provider_msg = "H5 核验未通过"
        enrollment.last_checked_at = ca_service._utcnow()
        await db.commit()
        return _callback_html("核验未完成", "请返回后重新发起或重试。")
    try:
        await ca_service.refresh_enrollment(enrollment)
        await db.commit()
    except FxqCaError:
        await db.rollback()
        return _callback_html("资料已提交", "放心签结果仍在异步生成，请稍后查询。")
    if enrollment.status == "succeeded":
        return _callback_html("身份核验成功", "CA 协议阅读和智能双录已经完成。")
    return _callback_html("资料已提交", "结果仍在异步生成，请稍后查询。")
