from datetime import date, datetime
from types import SimpleNamespace

from app.services.compliance_service import CN_TZ, build_regulatory_alerts


def _report(
    rid: int,
    *,
    method: str = "uploadRecipeIndicators",
    status: str = "success",
    biz_type: str = "recipe",
    batch_date: date | None = None,
):
    return SimpleNamespace(
        id=rid,
        method=method,
        status=status,
        biz_type=biz_type,
        batch_date=batch_date,
    )


def test_alerts_disabled_before_real_gateway_is_enabled():
    alerts = build_regulatory_alerts(
        [_report(1, status="dead")],
        enabled=False,
        now_cn=datetime(2026, 7, 26, 10, tzinfo=CN_TZ),
    )
    assert alerts == []


def test_consecutive_failures_stop_at_latest_success():
    signin_day = date(2026, 7, 25)
    reports = [
        _report(8, status="failed", method="methodA"),
        _report(7, status="dead", method="methodA"),
        _report(6, status="failed", method="methodA"),
        _report(5, status="success", method="methodB"),
        _report(4, status="failed", method="methodB"),
        _report(3, status="dead", method="methodB"),
        _report(2, status="failed", method="methodB"),
        _report(
            1,
            method="pushMedicalDispute",
            status="success",
            biz_type="dispute_signin",
            batch_date=signin_day,
        ),
    ]
    alerts = build_regulatory_alerts(
        reports,
        enabled=True,
        now_cn=datetime(2026, 7, 26, 10, tzinfo=CN_TZ),
        failure_threshold=3,
    )
    failures = [alert for alert in alerts if alert["code"] == "consecutive_failure"]
    assert [(alert["method"], alert["count"]) for alert in failures] == [("methodA", 3)]


def test_missing_and_incomplete_signin_are_distinguished():
    now_cn = datetime(2026, 7, 26, 10, tzinfo=CN_TZ)
    missing = build_regulatory_alerts([], enabled=True, now_cn=now_cn)
    assert missing[-1]["code"] == "signin_missing"
    assert "2026-07-25" in missing[-1]["title"]

    incomplete = build_regulatory_alerts(
        [
            _report(
                1,
                method="pushMedicalDispute",
                status="pending",
                biz_type="dispute_signin",
                batch_date=date(2026, 7, 25),
            )
        ],
        enabled=True,
        now_cn=now_cn,
    )
    assert incomplete[-1]["code"] == "signin_incomplete"


def test_before_deadline_checks_day_before_yesterday():
    alerts = build_regulatory_alerts(
        [
            _report(
                1,
                method="pushMedicalDispute",
                status="success",
                biz_type="dispute_signin",
                batch_date=date(2026, 7, 24),
            )
        ],
        enabled=True,
        now_cn=datetime(2026, 7, 26, 2, 59, tzinfo=CN_TZ),
        signin_deadline_hour=3,
    )
    assert alerts == []
