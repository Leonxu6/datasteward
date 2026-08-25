from pathlib import Path

from scripts.audit_repository_hygiene import audit_paths


def test_repository_hygiene_rejects_runtime_and_cache_paths():
    failures = audit_paths([Path(".env"), Path("transform/dbt/target/manifest.json"), Path("src/dm/main.py")])
    assert len(failures) == 2


def test_repository_hygiene_accepts_templates_and_source():
    assert audit_paths([Path(".env.example"), Path("deploy/role_map.yaml.template"), Path("src/dm/config.py")]) == []
