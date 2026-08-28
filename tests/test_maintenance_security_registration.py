from scripts.run_maintenance_audits import _ADVISORY_AUDITS, _AUDITS


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


def test_portability_and_process_blocking_audits_are_registered():
    expected = {
        "audit_path_text_encoding.py",
        "audit_open_text_encoding.py",
        "audit_naive_fromtimestamp.py",
        "audit_builtin_hash.py",
        "audit_tar_extractall.py",
        "audit_unpack_archive.py",
        "audit_os_chdir.py",
        "audit_os_umask.py",
        "audit_locale_mutation.py",
        "audit_warning_suppression.py",
        "audit_socket_default_timeout.py",
        "audit_signal_handlers.py",
        "audit_sys_exit.py",
        "audit_recursion_limit.py",
        "audit_gc_disable.py",
        "audit_random_seed.py",
        "audit_asyncio_run.py",
        "audit_logging_basic_config.py",
        "audit_subprocess_run_check.py",
        "audit_thread_daemon.py",
    }
    assert expected.issubset(set(_AUDITS))


def test_legacy_wide_audits_remain_visible_as_advisories():
    expected = {
        "audit_naive_datetime_now.py",
        "audit_environ_mutation.py",
        "audit_json_nan.py",
        "audit_sql_interpolation.py",
    }
    assert expected == set(_ADVISORY_AUDITS)
    assert expected.isdisjoint(set(_AUDITS))


def test_silent_exception_audit_remains_advisory():
    assert "audit_silent_exception.py" not in _AUDITS
