from dm.warehouse.store import _Conn


class CountingConnection:
    def __init__(self):
        self.close_calls = 0

    def close(self):
        self.close_calls += 1


def test_connection_close_only_delegates_once():
    raw = CountingConnection()
    conn = _Conn(raw)
    conn.close()
    conn.close()
    assert raw.close_calls == 1
