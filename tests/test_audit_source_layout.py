from pathlib import Path

from scripts.audit_source_layout import audit_paths


def test_source_layout_rejects_stray_src_modules():
    failures = audit_paths([Path("src/dm/__init__.py"), Path("src/helper.py")])
    assert failures == ["src/helper.py: Python source under src/ must belong to the dm package"]


def test_source_layout_requires_dm_initializer():
    assert audit_paths([Path("src/dm/config.py")]) == ["src/dm/__init__.py: package initializer is missing"]
