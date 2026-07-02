"""天津监管平台字段映射层（S3，docs/tianjin_supervision_plan.md）。

每个接口一个 build_xxx(entity...) -> dict，集中维护业务模型 → 规范字段的映射：
  - 机构三要素（organID/unitID/organName）统一注入；
  - 时间：库内 naive UTC → 北京时间 "YYYY-MM-DD HH:mm:ss"；金额：分 → 元两位小数；
  - 性别/证件等码值转换；身份证等密文字段在此解密（仅出现在上报 payload 中）；
  - 尚无数据来源的字段输出空串，由平台 -99 返回具体缺失项（测试期允许，S0 T6 补录后消除）。

纯函数：入参为 ORM 实体（或任何具备同名属性的对象），不做数据库访问——便于离线单测。
"""
from datetime import datetime, timedelta, timezone

from ..core.config import settings
from ..core.crypto import decrypt

CN_TZ = timezone(timedelta(hours=8))

# 复诊/咨询类别：我方业务映射（口径以 S0 T5 平台确认为准，此处集中一处便于切换）
CONSULT_TYPE_TEXT = "1"    # 图文咨询
RETURN_VISIT_VIDEO = "3"   # 复诊类别：视频交流
PAYMENT_CHANNEL_WX = "2"   # 支付渠道：微信
BUSINESS_TYPE = {"text": "1", "video": "4"}  # 评价/不良事件 businessType：1 图文咨询 / 4 在线复诊


def _cn(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.replace(tzinfo=timezone.utc).astimezone(CN_TZ).strftime("%Y-%m-%d %H:%M:%S")


def _now_cn() -> str:
    return datetime.now(CN_TZ).strftime("%Y-%m-%d %H:%M:%S")


def _yuan(fen: int | None) -> float:
    return round((fen or 0) / 100, 2)


def _sex(gender: str | None) -> str:
    return {"男": "1", "女": "2"}.get(gender or "", "0")


def _dec(enc: str | None) -> str:
    if not enc:
        return ""
    try:
        return decrypt(enc)
    except Exception:  # noqa: BLE001
        return ""


def _age_from_cert(cert_id: str) -> int:
    """18 位身份证 → 周岁；解析失败返回 0。"""
    try:
        birth = datetime.strptime(cert_id[6:14], "%Y%m%d").date()
        today = datetime.now(CN_TZ).date()
        return max(today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day)), 0)
    except (ValueError, IndexError):
        return 0


def _base() -> dict:
    return {
        "organID": settings.ORGAN_ID,
        "unitID": settings.TJ_UNIT_ID,
        "organName": settings.ORGAN_NAME,
    }


def _patient_fields(patient) -> dict:
    cert = _dec(getattr(patient, "id_card_enc", None)) if patient else ""
    return {
        "patientCertType": getattr(patient, "cert_type", None) or "1",
        "patientCertID": cert,
        "patientName": patient.name if patient else "",
        "age": _age_from_cert(cert),
        "sex": _sex(patient.gender if patient else None),
        "mobile": _dec(getattr(patient, "phone_enc", None)) if patient else "",
    }


def _doctor_fields(doctor, prefix: str = "doctor") -> dict:
    return {
        "subjectCode": getattr(doctor, "subject_code", None) or "" if doctor else "",
        "subjectName": getattr(doctor, "subject_name", None) or "" if doctor else "",
        "deptID": getattr(doctor, "dept_code", None) or "" if doctor else "",
        "deptName": (doctor.dept or "") if doctor else "",
        f"{prefix}Id": str(doctor.id) if doctor else "",
        f"{prefix}CertID": _dec(getattr(doctor, "id_card_enc", None)) if doctor else "",
        f"{prefix}Name": (doctor.name or "") if doctor else "",
    }


def _refuse_fields(order) -> dict:
    """取消/退款订单的拒绝三字段（终态非完成时填写）。"""
    from ..constants import OrderStatus
    if order.status not in (int(OrderStatus.REFUNDED), int(OrderStatus.CANCELLED)):
        return {}
    reason = order.cancel_reason or ""
    return {
        "refuseTime": _cn(order.finished_at),
        "refuseReason": reason,
        "refuseType": "2" if "超时" in reason else "1",
    }


# ---------- 2.2.1 在线咨询（图文） ----------
def build_consult(order, patient, doctor, rx=None) -> dict:
    answered = order.accepted_at is not None
    return {
        **_base(),
        "bussID": order.order_no,
        **_doctor_fields(doctor),
        **_patient_fields(patient),
        "consultationType": CONSULT_TYPE_TEXT,
        "onsultationAttribute": "1",  # 诊疗咨询（字段名为规范原文拼写）
        "applyDate": _cn(order.created_at),
        "startDate": _cn(order.accepted_at),
        "endDate": _cn(order.finished_at),
        "paymentChannel": PAYMENT_CHANNEL_WX,
        "consultationPrice": _yuan(order.register_fee_fen),
        "content": (rx.chief if rx and rx.chief else "在线问诊咨询"),
        "answerFlag": "1" if answered else "0",
        **_refuse_fields(order),
        "updateTime": _now_cn(),
    }


# ---------- 2.2.2 在线复诊（视频） ----------
def build_referral(order, patient, doctor, rx=None) -> dict:
    answered = order.accepted_at is not None
    diagnosis = (rx.icd_name or rx.diagnosis) if rx else None
    return {
        **_base(),
        "bussID": order.order_no,
        **_doctor_fields(doctor),
        # 本地路径（/uploads/…）说明尚未换取监管附件 id（采集器在网关可用时转换），不外发
        "firstDiagnosis": ("" if "/uploads/" in (order.first_diagnosis_file_ids or "")
                           else order.first_diagnosis_file_ids or ""),
        **_patient_fields(patient),
        "guardianCertID": _dec(getattr(patient, "guardian_cert_enc", None)) if patient else "",
        "guardianName": (getattr(patient, "guardian_name", None) or "") if patient else "",
        "guardianMobile": (getattr(patient, "guardian_mobile", None) or "") if patient else "",
        "returnVisitType": RETURN_VISIT_VIDEO,
        "diseasesHistory": (rx.present_illness if rx and rx.present_illness else "无"),
        "mainDiagnoseCode": (rx.icd_code.split("|")[0] if rx and rx.icd_code else ""),
        "thisDiagnosis": diagnosis or "无",
        "originalDiagnosis": order.original_diagnosis or "",
        "referralFlag": "0" if order.referral_flag is False else "1",  # 未声明视为复诊（业务准入即复诊）
        "applyDate": _cn(order.created_at),
        "startDate": _cn(order.accepted_at),
        "endDate": _cn(order.finished_at),
        "diagNoFillReason": "" if diagnosis else "问诊未完成或无需处方",
        "paymentChannel": PAYMENT_CHANNEL_WX,
        "returnVisitPrice": _yuan(order.register_fee_fen),
        "answerFlag": "1" if answered else "0",
        **_refuse_fields(order),
        "updateTime": _now_cn(),
    }


# ---------- 2.2.10 电子病历 ----------
def build_emr(order, patient, doctor, rx) -> dict:
    cert = _dec(getattr(patient, "id_card_enc", None)) if patient else ""
    return {
        **_base(),
        "deptID": getattr(doctor, "dept_code", None) or "" if doctor else "",
        "deptName": (doctor.dept or "") if doctor else "",
        "caseNo": f"EMR{rx.id}",
        "doctorID": str(doctor.id) if doctor else "",
        "doctorName": (doctor.name or "") if doctor else "",
        "doctorCertID": _dec(getattr(doctor, "id_card_enc", None)) if doctor else "",
        "furtherConsultNo": order.order_no,
        "diagnosisCode": rx.icd_code or "",
        "furtherConsultDiagnosis": rx.icd_name or rx.diagnosis or "",
        "visitDate": _cn(order.accepted_at)[:10],
        "patientName": patient.name if patient else "",
        "patientSex": _sex(patient.gender if patient else None),
        "patientAge": _age_from_cert(cert),
        "patientIdcardType": getattr(patient, "cert_type", None) or "1",
        "patientIdcardNum": cert,
        "phone": _dec(getattr(patient, "phone_enc", None)) if patient else "",
        "chiefComplaint": rx.chief or "",
        "presentHistory": rx.present_illness or "",
        "diagnosticOpinion": rx.advice or "",
        "updateTime": _now_cn(),
    }


# ---------- 2.2.3 在线处方 ----------
def build_recipe(order, patient, doctor, rx, pharmacist=None) -> dict:
    from ..constants import OrderStatus
    is_paid = order.status == int(OrderStatus.FINISHED)
    datein = _cn(rx.checked_at or rx.created_at)
    items = []
    for it in (rx.items or []):
        items.append({
            "drcode": str(it.get("drug_id") or it.get("name", "")),
            "drname": it.get("name", ""),
            "drmodel": it.get("spec") or "",
            "admission": it.get("usage") or "口服",
            "frequency": it.get("frequency") or it.get("usage") or "",
            "dosage": str(it.get("dosage") or "1"),
            "drunit": it.get("drunit") or "",
            "dosageTotal": it.get("qty", 1),
            "doseUnit": it.get("dose_unit") or "盒",
            "useDays": it.get("use_days") or 3,
            "otcFlag": "0",
        })
    return {
        **_base(),
        "bussID": order.order_no,
        "bussSource": "4" if order.consult_type == "video" else "1",
        **_doctor_fields(doctor),
        "auditDoctorId": str(pharmacist.id) if pharmacist else "",
        "auditDoctorCertID": _dec(getattr(pharmacist, "id_card_enc", None)) if pharmacist else "",
        "auditDoctor": (pharmacist.name or pharmacist.username) if pharmacist else "",
        "checkDate": _cn(rx.checked_at),
        "patientCardType": getattr(patient, "cert_type", None) or "1",
        **{k: v for k, v in _patient_fields(patient).items() if k != "patientCertType"},
        "guardianCertID": _dec(getattr(patient, "guardian_cert_enc", None)) if patient else "",
        "guardianName": (getattr(patient, "guardian_name", None) or "") if patient else "",
        "diseasesHistory": rx.present_illness or "无",
        "recipeUniqueID": rx.recipe_unique_id or "",
        "recipeID": str(rx.id),
        "recipeStatus": "1",
        "rationalFlag": "0",  # 暂未接入合理用药系统
        "icdCode": rx.icd_code or "",
        "icdName": rx.icd_name or rx.diagnosis or "",
        "recipeType": "1",
        "datein": datein,
        "effectivePeriod": 3,
        "startDate": datein[:10],
        "endDate": _cn((rx.checked_at or rx.created_at) + timedelta(days=3))[:10] if (rx.checked_at or rx.created_at) else "",
        "totalFee": _yuan(order.drug_fee_fen),
        "isPay": "1" if is_paid else "0",
        "verificationStatus": "1" if is_paid else "0",
        "orderList": items,
        "updateTime": _now_cn(),
    }


# ---------- 2.2.4 处方核销 ----------
def build_verification(order, rx) -> dict:
    return {
        **_base(),
        "bussID": order.order_no,
        "recipeUniqueID": rx.recipe_unique_id or "",
        "recipeID": str(rx.id),
        "deliveryType": "1",  # 医院药房物流配送（口径确认后如需自取改 0）
        "VerificationTime": _cn(order.finished_at),
        "deliveryFirm": settings.ORGAN_NAME + "药房" if settings.ORGAN_NAME else "医院药房",
        "deliveryPeople": "药房",
        "deliverySTDate": _cn(order.finished_at),
        "deliveryENDDate": "",  # M7 物流签收落地后回填
        "totalFee": _yuan(order.drug_fee_fen),
        "isPay": "1",
        "tradeNo": order.wx_drug_transaction_id or "",
        "updateTime": _now_cn(),
    }


# ---------- 2.4.1 评价信息 ----------
def build_evaluation(ev, order, doctor) -> dict:
    return {
        **_base(),
        "evaluateID": str(ev.id),
        "bussID": order.order_no if order else "",
        "businessType": BUSINESS_TYPE.get(order.consult_type if order else "", "99"),
        "deptID": getattr(doctor, "dept_code", None) or "" if doctor else "",
        "deptName": (doctor.dept or "") if doctor else "",
        "doctorId": str(doctor.id) if doctor else "",
        "doctorCertID": _dec(getattr(doctor, "id_card_enc", None)) if doctor else "",
        "doctorName": (doctor.name or "") if doctor else "",
        "satisfaction": ev.satisfaction,
        "scoring": ev.scoring,
        "evaluation": ev.content,
        "complaints": ev.complaints or "",
        "evaluationPeople": ev.evaluator or "患者",
        "evaluationTime": _cn(ev.created_at),
        "updateTime": _now_cn(),
    }


# ---------- 2.4.2 医疗争议（不良事件） ----------
def build_dispute(d) -> dict:
    return {
        "organID": settings.ORGAN_ID,
        "unitID": settings.TJ_UNIT_ID,
        "eventID": str(d.id),
        "businessType": d.business_type,
        "patientName": d.patient_name,
        "mobile": d.mobile,
        "eventDescription": d.event_description,
        "eventDate": _cn(d.event_date),
        "eventReason": d.event_reason,
        "takeSteps": d.take_steps,
        "damageDegree": d.damage_degree,
        "Improvements": d.improvements,  # 首字母大写为规范原文
        "reportDept": d.report_dept,
        "reportPerson": d.report_person,
        "reportDate": _cn(d.report_date or d.created_at),
        "updateTime": _now_cn(),
    }


# ---------- 2.1.1 药品目录 ----------
def build_drug(drug, use_flag: str | None = None) -> dict:
    return {
        **_base(),
        "drugClass": drug.drug_class or "",
        "countrydrcode": drug.countrydrcode or "",
        "hospDrcode": str(drug.id),
        "hospDrugName": drug.name,
        "hospDrugPacking": drug.packing or drug.spec or "",
        "hospDrugManuf": drug.manufacturer or "",
        "drugPrice": _yuan(drug.price_fen),
        "useFlag": use_flag or drug.use_flag or "1",
        "updateTime": _now_cn(),
    }
