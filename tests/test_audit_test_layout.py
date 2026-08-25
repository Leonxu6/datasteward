from pathlib import Path

from scripts.audit_test_layout import audit_paths


def test_test_layout_rejects_nonstandard_modules():
    assert audit_paths([Path("tests/helpers.py"), Path("tests/test_ok.py")]) == ["tests/helpers.py: test module must start with test_"]


def test_test_layout_allows_package_initializer():
    assert audit_paths([Path("tests/__init__.py"), Path("tests/test_ok.py")]) == []
