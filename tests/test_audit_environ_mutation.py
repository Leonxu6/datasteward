from scripts.audit_environ_mutation import audit_source


def test_environ_audit_allows_environment_reads():
    assert audit_source("value = os.environ.get('NAME')\n") == []


def test_environ_audit_reports_process_mutations():
    assert audit_source("os.environ['NAME'] = 'value'\nos.environ.update({'X':'1'})\n") == [
        "os.environ assignment mutates process state on line 1",
        "os.environ.update() mutates process state on line 2",
    ]
