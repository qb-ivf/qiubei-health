"""天津监管字段映射层单测（纯函数，SimpleNamespace 模拟实体，无需数据库）。"""
from datetime import datetime
from types import SimpleNamespace

from app.services.tj_mappers import (
    _age_from_cert,
    _cn,
    _sex,
    _yuan,
    build_consult,
    build_dispute,
    build_drug,
    build_recipe,
    build_referral,
)


def _order(**kw):
    base = dict(
        id=1, order_no="REGABC123", status=6, consult_type="video",
        created_at=datetime(2026, 7, 1, 2, 0, 0), accepted_at=datetime(2026, 7, 1, 2, 5, 0),
        finished_at=datetime(2026, 7, 1, 2, 20, 0), cancel_reason=None,
        register_fee_fen=5000, drug_fee_fen=12080,
        referral_flag=None, original_diagnosis="上呼吸道感染",
        first_diagnosis_file_ids="F1,F2", wx_drug_transaction_id="4200001234",
    )
    base.update(kw)
    return SimpleNamespace(**base)


def _patient():
    return SimpleNamespace(
        name="张三", gender="男", id_card_enc=None, phone_enc=None, cert_type="1",
        guardian_name=None, guardian_cert_enc=None, guardian_mobile=None,
    )


def _doctor():
    return SimpleNamespace(
        id=7, name="李医生", dept="呼吸内科", subject_code="03.01",
        subject_name="呼吸内科专业", dept_code="03", id_card_enc=None,
    )


def _rx(**kw):
    base = dict(
        id=55, chief="咳嗽三天", present_illness="干咳无痰", diagnosis="急性支气管炎",
        advice="多饮水", icd_code="J20.900|J06.900", icd_name="急性支气管炎|急性上呼吸道感染",
        items=[{"name": "阿莫西林胶囊", "spec": "0.25g*24粒", "qty": 2, "usage": "口服 每日3次", "price_fen": 1080}],
        checked_at=datetime(2026, 7, 1, 3, 0, 0), created_at=datetime(2026, 7, 1, 2, 30, 0),
        recipe_unique_id="abcd1234", audit_status="approved",
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_helpers():
    assert _yuan(12080) == 120.80
    assert _yuan(None) == 0
    assert _sex("男") == "1" and _sex("女") == "2" and _sex(None) == "0"
    # naive UTC 2026-07-01 02:00 → 北京时间 10:00
    assert _cn(datetime(2026, 7, 1, 2, 0, 0)) == "2026-07-01 10:00:00"
    assert _cn(None) == ""
    assert _age_from_cert("11010120000101001X") >= 26
    assert _age_from_cert("bad") == 0


def test_build_referral_video_order():
    p = build_referral(_order(), _patient(), _doctor(), _rx())
    assert p["bussID"] == "REGABC123"
    assert p["returnVisitType"] == "3"
    assert p["mainDiagnoseCode"] == "J20.900"          # 多诊断取第一个
    assert p["referralFlag"] == "1"                    # 未声明视为复诊
    assert p["firstDiagnosis"] == "F1,F2"
    assert p["startDate"] == "2026-07-01 10:05:00"     # UTC→北京时间
    assert p["returnVisitPrice"] == 50.0
    assert p["answerFlag"] == "1"
    assert "refuseTime" not in p                       # 完成单无拒绝字段


def test_build_consult_cancelled_has_refuse_fields():
    o = _order(consult_type="text", status=9, accepted_at=None, cancel_reason="超时未支付自动取消")
    p = build_consult(o, _patient(), _doctor(), None)
    assert p["consultationType"] == "1"
    assert p["answerFlag"] == "0"
    assert p["refuseType"] == "2"                      # 超时 → 系统自动拒绝
    assert p["refuseReason"] == "超时未支付自动取消"
    assert p["content"] == "在线问诊咨询"               # 无病历时的兜底文案


def test_build_recipe():
    pharmacist = SimpleNamespace(id=3, name="王药师", username="pharm01", id_card_enc=None)
    p = build_recipe(_order(), _patient(), _doctor(), _rx(), pharmacist)
    assert p["recipeUniqueID"] == "abcd1234"
    assert p["recipeType"] == "1" and p["bussSource"] == "4"
    assert p["totalFee"] == 120.80 and p["isPay"] == "1"
    assert p["auditDoctor"] == "王药师" and p["checkDate"] == "2026-07-01 11:00:00"
    item = p["orderList"][0]
    assert item["drname"] == "阿莫西林胶囊" and item["dosageTotal"] == 2
    assert item["admission"] == "口服 每日3次"


def test_build_dispute_spec_key_casing():
    d = SimpleNamespace(
        id=9, business_type="4", patient_name="张三", mobile="13800000000",
        event_description="视频中断", event_date=datetime(2026, 7, 1, 2, 0, 0),
        event_reason="网络故障", take_steps="电话回访", damage_degree="无损害",
        improvements="增加重连机制", report_dept="医务科", report_person="赵主任",
        report_date=None, created_at=datetime(2026, 7, 1, 6, 0, 0),
    )
    p = build_dispute(d)
    assert p["Improvements"] == "增加重连机制"          # 规范原文首字母大写
    assert p["eventDate"] == "2026-07-01 10:00:00"
    assert p["reportDate"] == "2026-07-01 14:00:00"    # 缺省取 created_at


def test_build_drug_use_flag_override():
    drug = SimpleNamespace(
        id=11, name="阿莫西林胶囊", spec="0.25g*24粒", price_fen=1080,
        drug_class="010101", countrydrcode="", packing=None, manufacturer="测试药厂", use_flag="1",
    )
    p = build_drug(drug)
    assert p["hospDrcode"] == "11" and p["drugPrice"] == 10.80
    assert p["hospDrugPacking"] == "0.25g*24粒"        # packing 空回退 spec
    assert build_drug(drug, use_flag="2")["useFlag"] == "2"  # 删除→目录取消
