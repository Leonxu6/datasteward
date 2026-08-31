from dm.tools.audit_record import elapsed_ms


def test_elapsed_ms_does_not_treat_booleans_as_clock_values():
    assert elapsed_ms(True, 2.0) == 0
    assert elapsed_ms(1.0, False) == 0
