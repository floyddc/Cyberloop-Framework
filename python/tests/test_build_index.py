import unittest
from unittest.mock import patch

from RAG import build_index


class BuildIndexTests(unittest.TestCase):
    @patch("RAG.build_index.index_records", return_value=2)
    @patch("RAG.build_index.build_chunks", return_value=[{"id": "a"}, {"id": "b"}])
    @patch(
        "RAG.build_index.load_new_database_documents",
        return_value=(
            [],
            [{"id": 8}],
            [{"id": 14}],
        ),
    )
    @patch("RAG.build_index.IndexStateStore")
    def test_uses_postgres_cursors_and_advances_after_successful_index(
        self,
        state_store_class,
        load_new_documents,
        build_chunks,
        index_records,
    ):
        state_store = state_store_class.return_value
        state_store.get_cursor.side_effect = [5, 10]

        build_index.main()

        self.assertEqual(
            state_store.get_cursor.call_args_list[0].args,
            ("kb_documents",),
        )
        self.assertEqual(
            state_store.get_cursor.call_args_list[1].args,
            ("incident_history",),
        )
        load_new_documents.assert_called_once_with(5, 10)
        build_chunks.assert_called_once_with([])
        index_records.assert_called_once_with([{"id": "a"}, {"id": "b"}])
        state_store.advance_cursor.assert_any_call("kb_documents", 8)
        state_store.advance_cursor.assert_any_call("incident_history", 14)


if __name__ == "__main__":
    unittest.main()
