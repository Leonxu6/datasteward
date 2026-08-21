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

    @patch("dm.docs.store._ddl", return_value=["first", "second"])
    @patch("dm.docs.store.connect")
    def test_init_schema_closes_resources_after_success(self, connect, _ddl):
        cursor = Mock()
        conn = Mock()
        conn.cursor.return_value = cursor
        connect.return_value = conn

        store.init_schema()

        self.assertEqual([item.args[0] for item in cursor.execute.call_args_list], ["first", "second"])
        cursor.close.assert_called_once_with()
        conn.close.assert_called_once_with()

    @patch("dm.docs.store._ddl", return_value=["first", "second"])
    @patch("dm.docs.store.connect")
    def test_init_schema_closes_resources_after_ddl_failure(self, connect, _ddl):
        cursor = Mock()
        cursor.execute.side_effect = RuntimeError("ddl failed")
        conn = Mock()
        conn.cursor.return_value = cursor
        connect.return_value = conn

        with self.assertRaisesRegex(RuntimeError, "ddl failed"):
            store.init_schema()

        cursor.close.assert_called_once_with()
        conn.close.assert_called_once_with()

    @patch("dm.docs.store.connect")
    def test_counts_returns_document_and_chunk_counts(self, connect):
        cursor = Mock()
        cursor.fetchone.side_effect = [(3,), (17,)]
        conn = Mock()
        conn.cursor.return_value = cursor
        connect.return_value = conn

        self.assertEqual(store.counts(), (3, 17))
        self.assertEqual(
            [item.args[0] for item in cursor.execute.call_args_list],
            ["SELECT count(*) FROM document", "SELECT count(*) FROM doc_chunk"],
        )
        cursor.close.assert_called_once_with()
        conn.close.assert_called_once_with()

    @patch("dm.docs.store.connect")
    def test_counts_closes_resources_when_query_fails(self, connect):
        cursor = Mock()
        cursor.execute.side_effect = RuntimeError("query failed")
        conn = Mock()
        conn.cursor.return_value = cursor
        connect.return_value = conn

        with self.assertRaisesRegex(RuntimeError, "query failed"):
            store.counts()

        cursor.close.assert_called_once_with()
        conn.close.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
