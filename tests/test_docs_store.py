import unittest
from unittest.mock import Mock, patch

from dm.docs import store


class DocumentStoreTests(unittest.TestCase):
    @patch("pgvector.psycopg2.register_vector", side_effect=RuntimeError("bad vector"))
    @patch("dm.docs.store.connect")
    def test_connect_vec_closes_connection_on_registration_failure(self, connect, _register):
        conn = Mock()
        connect.return_value = conn

        with self.assertRaisesRegex(RuntimeError, "bad vector"):
            store.connect_vec(autocommit=False)

        connect.assert_called_once_with(autocommit=False)
        conn.close.assert_called_once_with()

    @patch("pgvector.psycopg2.register_vector")
    @patch("dm.docs.store.connect")
    def test_connect_vec_returns_registered_connection(self, connect, register):
        conn = Mock()
        connect.return_value = conn

        self.assertIs(store.connect_vec(), conn)

        register.assert_called_once_with(conn)
        conn.close.assert_not_called()


if __name__ == "__main__":
    unittest.main()
