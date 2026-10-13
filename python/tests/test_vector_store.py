import unittest
from unittest.mock import patch

from RAG.vector_store import index_records


class VectorStoreTests(unittest.TestCase):
    @patch("RAG.vector_store.embed_texts", return_value=[[0.1]])
    @patch("RAG.vector_store.get_collection")
    def test_indexes_only_records_missing_from_chroma(self, get_collection, embed_texts):
        collection = get_collection.return_value
        collection.get.return_value = {"ids": ["already-indexed"]}
        records = [
            {"id": "already-indexed", "text": "old", "metadata": {"category": "docs"}},
            {"id": "new-record", "text": "new", "metadata": {"category": "docs"}},
        ]

        indexed = index_records(records)

        self.assertEqual(indexed, 1)
        embed_texts.assert_called_once_with(["new"])
        collection.upsert.assert_called_once()
        self.assertEqual(collection.upsert.call_args.kwargs["ids"], ["new-record"])

    @patch("RAG.vector_store.embed_texts")
    @patch("RAG.vector_store.get_collection")
    def test_skips_embedding_when_every_record_already_exists(self, get_collection, embed_texts):
        collection = get_collection.return_value
        collection.get.return_value = {"ids": ["existing"]}

        indexed = index_records(
            [{"id": "existing", "text": "old", "metadata": {"category": "docs"}}]
        )

        self.assertEqual(indexed, 0)
        embed_texts.assert_not_called()
        collection.upsert.assert_not_called()


if __name__ == "__main__":
    unittest.main()
