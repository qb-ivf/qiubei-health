import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
FONT = BACKEND / "app" / "static" / "material-symbols-outlined-subset.woff2"
FONT_SHA256 = "1912ddef81b71dc91739c657f39a4bfbc62c53213d1b5de94a91da7ce2a99392"


def test_material_symbols_subset_is_vendored_with_expected_digest():
    assert FONT.is_file()
    assert hashlib.sha256(FONT.read_bytes()).hexdigest() == FONT_SHA256


def test_mini_programs_use_first_party_font_url():
    for project in ("miniprogram-patient", "miniprogram-doctor"):
        app_js = (ROOT / project / "app.js").read_text(encoding="utf-8")
        assert "https://api.qb-medical.cn/static/material-symbols-outlined-subset.woff2" in app_js
        assert "cdn.jsdelivr.net" not in app_js
