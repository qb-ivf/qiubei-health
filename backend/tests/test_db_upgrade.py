from pathlib import Path

from scripts.db_upgrade import VERSION_TABLE, alembic_config, classify_schema


def test_classify_empty_schema():
    assert classify_schema(set()) == "empty"


def test_classify_legacy_schema():
    assert classify_schema({"users", "orders"}) == "legacy"


def test_classify_versioned_schema_takes_precedence():
    assert classify_schema({VERSION_TABLE, "users"}) == "versioned"


def test_alembic_config_points_to_repository_scripts():
    script_location = Path(alembic_config().get_main_option("script_location"))
    assert script_location.name == "alembic"
    assert (script_location / "versions" / "20260726_01_current_schema_baseline.py").is_file()
