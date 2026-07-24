"""天津监管测试环境联调冒烟脚本（S5）：9 个必接接口各推 1 条测试数据。

与 tj_ping 的区别：payload 由生产映射层 tj_mappers 构建（端到端验证真实映射代码），
数据带明显测试标记（患者"测试患者"、订单号 QBTEST 前缀），平台反显页可辨识。

用法（配置自动读 backend/.env，同 tj_ping）：
    python scripts/tj_smoke.py --dry     # 只打印各接口 payload，不发送（本地验证映射）
    python scripts/tj_smoke.py           # 真实推送 9 个接口各 1 条到测试网关（正式网关强制拒绝）
    服务器： dc exec api python scripts/tj_smoke.py

判读：每行 [接口] msgCode=200 为通过；-99 时 msg 列出缺失字段名（逐个补齐即可）。
可重复运行：每次生成新的唯一业务号（QBTEST+时间戳），不会与上次冲突。
"""
import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # backend/

from scripts.tj_ping import APP_KEY, APP_SECRET, GATEWAY  # noqa: E402  复用 .env 配置加载
from app.services import tj_mappers as m  # noqa: E402
from app.services.tj_config import is_production_gateway  # noqa: E402
from app.utils.sm_crypto import build_sign_headers, sm3_hex_upper, sm4_cbc_encrypt_hex  # noqa: E402

NOW = datetime.now(timezone.utc).replace(tzinfo=None)


def _valid_cert(seed17: str) -> str:
    """按 GB11643 计算校验位，生成格式合法的测试身份证号。"""
    w = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
    s = sum(int(c) * w[i] for i, c in enumerate(seed17))
    return seed17 + "10X98765432"[s % 11]


PATIENT_CERT = _valid_cert("12010119900101001")   # 测试患者
DOCTOR_CERT = _valid_cert("12010119800101002")    # 测试医生
PHARMACIST_CERT = _valid_cert("12010119850101003")  # 测试药师
TEST_MOBILE = "13800000000"


# —— 用 SimpleNamespace 构造测试实体（与单测同法，走真实映射层） ——
def _entities(seq: str):
    order = SimpleNamespace(
        id=0, order_no=f"QBTEST{seq}", status=6, consult_type="video",
        created_at=NOW - timedelta(hours=3), paid_at=NOW - timedelta(hours=3),
        accepted_at=NOW - timedelta(hours=2), finished_at=NOW - timedelta(hours=1),
        cancel_reason=None, register_fee_fen=5000, drug_fee_fen=2160,
        referral_flag=True, original_diagnosis="急性上呼吸道感染（测试）",
        first_diagnosis_file_ids="", wx_transaction_id=f"420000TEST{seq}",
        wx_drug_transaction_id=f"420000TESTD{seq}",
    )
    patient = SimpleNamespace(
        name="测试患者", gender="男", id_card_enc=None, phone_enc=None, cert_type="1",
        guardian_name=None, guardian_cert_enc=None, guardian_mobile=None,
    )
    doctor = SimpleNamespace(
        id=9001, name="测试医生", dept="内科", subject_code="03", subject_name="内科",
        dept_code="03", id_card_enc=None,
    )
    rx = SimpleNamespace(
        id=int(seq), chief="咳嗽三天（测试）", present_illness="干咳无痰（测试数据）",
        diagnosis="急性上呼吸道感染", advice="多饮水，注意休息（测试）",
        icd_code="J06.900", icd_name="急性上呼吸道感染",
        items=[{"drug_id": 1, "name": "阿莫西林胶囊", "spec": "0.25g*24粒", "qty": 2,
                "usage": "口服", "frequency": "一日三次，一次一粒", "dosage": "1", "drunit": "粒",
                "dose_unit": "盒", "use_days": 3, "price_fen": 1080}],
        checked_at=NOW - timedelta(minutes=50), created_at=NOW - timedelta(hours=1),
        recipe_unique_id=f"qbtest{seq}", audit_status="approved",
    )
    pharmacist = SimpleNamespace(id=9002, name="测试药师", username="testpharm", id_card_enc=None)
    slot = SimpleNamespace(day=time.strftime("%Y-%m-%d"), start_time="09:00", end_time="09:30")
    ev = SimpleNamespace(
        id=int(seq), satisfaction=5, scoring=10, content="服务很好（联调测试评价）",
        complaints=None, evaluator="测试患者", created_at=NOW - timedelta(minutes=30),
    )
    dispute = SimpleNamespace(
        id=int(seq), business_type="4", patient_name="测试患者", mobile=TEST_MOBILE,
        event_description="联调测试事件（非真实）", event_date=NOW - timedelta(hours=2),
        event_reason="联调测试", take_steps="联调测试", damage_degree="无损害",
        improvements="无（联调测试）", report_dept="医务科", report_person="测试上报人",
        report_date=None, created_at=NOW,
    )
    drug = SimpleNamespace(
        id=990001, name="阿莫西林胶囊(联调测试)", spec="0.25g*24粒", price_fen=1080,
        drug_class="010101", countrydrcode="", packing="0.25g*24粒/盒",
        manufacturer="联调测试厂家", use_flag="2",  # 取消态，不污染目录
    )
    return order, patient, doctor, rx, pharmacist, slot, ev, dispute, drug


def _patch(p: dict, **certs) -> dict:
    """补上测试证件号/手机号（实体的 *_enc 为空，映射输出空串，此处直接覆写）。"""
    for k, v in certs.items():
        if k in p:
            p[k] = v
    return p


def build_all(seq: str) -> list[tuple[str, list]]:
    order, patient, doctor, rx, pharmacist, slot, ev, dispute, drug = _entities(seq)
    text_order = SimpleNamespace(**{**order.__dict__, "consult_type": "text",
                                    "order_no": f"QBTESTC{seq}"})
    cert = dict(patientCertID=PATIENT_CERT, doctorCertID=DOCTOR_CERT, mobile=TEST_MOBILE)
    return [
        ("uploadDrugCatalogue", [m.build_drug(drug)]),
        ("uploadConsultIndicators", [_patch(m.build_consult(text_order, patient, doctor, rx), **cert)]),
        ("uploadReferralIndicators", [_patch(m.build_referral(order, patient, doctor, rx), **cert)]),
        ("uploadElectMedicalRecord", [_patch(m.build_emr(order, patient, doctor, rx),
                                             patientIdcardNum=PATIENT_CERT, doctorCertID=DOCTOR_CERT,
                                             phone=TEST_MOBILE)]),
        ("uploadRecipeIndicators", [_patch(m.build_recipe(order, patient, doctor, rx, pharmacist),
                                           patientCertID=PATIENT_CERT, doctorCertID=DOCTOR_CERT,
                                           auditDoctorCertID=PHARMACIST_CERT, mobile=TEST_MOBILE)]),
        ("uploadRecipeVerificationIndicators", [m.build_verification(order, rx)]),
        ("uploadBusinessInfoAfter", [_patch(m.build_evaluation(ev, order, doctor), doctorCertID=DOCTOR_CERT)]),
        ("pushMedicalDispute", [m.build_dispute(dispute)]),
        ("uploadAppointRecord", [_patch(m.build_appoint(order, patient, doctor, slot), **cert)]),
    ]


def send(method: str, payload: list) -> str:
    import httpx
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    enc = sm4_cbc_encrypt_hex(body, APP_SECRET)
    headers = build_sign_headers(method, sm3_hex_upper(enc), APP_KEY)
    r = httpx.post(GATEWAY, content=enc, headers=headers, timeout=30)
    return r.text.strip()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true", help="只打印 payload 不发送")
    parser.add_argument("--count", type=int, default=1,
                        help="轮数：每轮 9 接口各 1 条（刷达标量用，如 --count 50）")
    args = parser.parse_args()

    if args.dry:
        for method, payload in build_all(time.strftime("%m%d%H%M%S") + "00"):
            print(f"\n===== {method} =====")
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        print("\n共 9 个接口 payload 构建成功（--dry 未发送）")
        sys.exit(0)

    if is_production_gateway(GATEWAY):
        print("拒绝向正式网关推送九接口合成测试数据。请切回测试网关运行 tj_smoke，")
        print("正式环境使用 tj_preflight + tj_bootstrap_drugs，并由真实业务批次验证。")
        sys.exit(2)

    base = time.strftime("%m%d%H%M%S")
    print(f"批次标识 QBTEST{base}xx → {GATEWAY}（{args.count} 轮）\n")
    ok = total = 0
    fail_methods: dict[str, str] = {}
    for i in range(args.count):
        seq = f"{base}{i:02d}"
        for method, payload in build_all(seq):
            resp = send(method, payload)
            passed = '"msgCode":200' in resp
            ok += passed
            total += 1
            if not passed:
                fail_methods[method] = resp[:220]
            if args.count == 1:
                print(f"{'✅' if passed else '❌'} {method}: {resp[:220]}")
            time.sleep(1)  # 温和限速
        if args.count > 1:
            print(f"第 {i + 1}/{args.count} 轮完成（累计通过 {ok}/{total}）")
    print(f"\n通过 {ok}/{total}。")
    for method, resp in fail_methods.items():
        print(f"  ❌ {method}: {resp}")
    if fail_methods:
        print("未通过的看 msg 提示的缺失字段，修正映射后重跑即可。")
