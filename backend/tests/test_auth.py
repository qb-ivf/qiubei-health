"""M1 鉴权/加密/实名 纯逻辑测试（无需数据库）。"""
from app.core.crypto import decrypt, encrypt
from app.core.security import create_token, decode_token, mask_id_card, mask_phone
from app.services.patient_service import real_name_verify


def test_jwt_roundtrip():
    token = create_token(sub="42", role="patient")
    payload = decode_token(token)
    assert payload["sub"] == "42"
    assert payload["role"] == "patient"


def test_jwt_invalid():
    assert decode_token("not-a-token") is None


def test_crypto_roundtrip():
    raw = "120101199001011234"
    enc = encrypt(raw)
    assert enc != raw
    assert decrypt(enc) == raw


def test_real_name_verify():
    assert real_name_verify("张三", "12010119900101123X")
    assert not real_name_verify("张三", "123")        # 长度不对
    assert not real_name_verify("", "120101199001011234")  # 姓名空


def test_mask():
    assert mask_phone("13812345678") == "138****5678"
    assert mask_id_card("120101199001011234").endswith("1234")
    assert "*" in mask_id_card("120101199001011234")
