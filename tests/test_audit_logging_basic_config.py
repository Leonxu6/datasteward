from scripts.audit_logging_basic_config import audit_source


def test_logging_audit_allows_module_loggers():
    assert audit_source("logger = logging.getLogger(__name__)\n") == []


def test_logging_audit_reports_basic_config():
    assert audit_source("logging.basicConfig(level=logging.INFO)\n") == [
        "logging.basicConfig() mutates process-wide logging on line 1"
    ]
