from scripts.run_maintenance_audits import _AUDITS


def test_new_syntax_supply_chain_and_security_audits_are_registered():
    expected = {
        "audit_json_syntax.py", "audit_toml_syntax.py", "audit_unicode_bidi.py",
        "audit_dynamic_code.py", "audit_subprocess_shell.py", "audit_unsafe_deserialization.py",
        "audit_weak_hash.py", "audit_tls_verification.py", "audit_tempfile_safety.py",
        "audit_dependency_sources.py", "audit_markdown_fences.py", "audit_merge_markers.py",
        "audit_yaml_loading.py", "audit_unicode_paths.py", "audit_symlink_targets.py",
    }
    assert expected.issubset(set(_AUDITS))


def test_reliability_and_async_audits_are_registered():
    expected = {
        "audit_bare_except.py",
        "audit_mutable_default.py",
        "audit_wildcard_import.py",
        "audit_debug_calls.py",
        "audit_os_system.py",
        "audit_datetime_utcnow.py",
        "audit_absolute_user_paths.py",
        "audit_duplicate_definitions.py",
        "audit_unsafe_chmod.py",
        "audit_http_timeout.py",
        "audit_urlopen_timeout.py",
        "audit_subprocess_timeout.py",
        "audit_async_blocking_sleep.py",
        "audit_async_subprocess.py",
    }
    assert expected.issubset(set(_AUDITS))


def test_silent_exception_audit_remains_advisory():
    assert "audit_silent_exception.py" not in _AUDITS
