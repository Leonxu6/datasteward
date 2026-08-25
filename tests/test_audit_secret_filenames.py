from pathlib import Path

from scripts.audit_secret_filenames import audit_paths


def test_secret_filename_audit_flags_private_material():
    assert len(audit_paths([Path("client.pem"), Path("credentials.json"), Path("src/dm/config.py")])) == 2


def test_secret_filename_audit_accepts_templates():
    assert audit_paths([Path(".env.example"), Path("deploy/role_map.yaml.template")]) == []
