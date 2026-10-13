import unittest
from unittest.mock import Mock, patch

from RAG.context_builder import alert_to_query, retrieve_context
from RAG.retriever import format_context, retrieve


class RagContextTests(unittest.TestCase):
    def test_formatted_context_omits_sources_links_and_citations(self):
        context = format_context(
            [
                {
                    "metadata": {"source": "internal/path/document.md"},
                    "text": (
                        "[Incident guide](https://example.test/guide) says review [1].\n"
                        "More: https://example.test/reference"
                    ),
                }
            ]
        )

        self.assertEqual(context, "Incident guide says review .\nMore:")
        self.assertNotIn("source:", context)
        self.assertNotIn("example.test", context)
        self.assertNotIn("[1]", context)

    def test_alert_query_requires_customer_and_excludes_metadata(self):
        with self.assertRaisesRegex(ValueError, "customer"):
            alert_to_query({"host": "endpoint-1"})

        customer, query = alert_to_query(
            {
                "customer": "tenant-a",
                "_source": "EDR",
                "external_id": "alert-17",
                "host": "endpoint-1",
            }
        )

        self.assertEqual(customer, "tenant-a")
        self.assertEqual(query, '{"host": "endpoint-1"}')

    @patch("RAG.context_builder.ContextBuilder")
    def test_prompt_context_function_returns_formatted_context(self, builder_class):
        builder_class.return_value.build.return_value = "Relevant guidance"

        context = retrieve_context({"customer": "tenant-a", "alert": "suspicious login"})

        self.assertEqual(context, "Relevant guidance")
        builder_class.return_value.build.assert_called_once_with(
            {"customer": "tenant-a", "alert": "suspicious login"}
        )

    @patch("RAG.retriever.rerank", side_effect=lambda query, hits, top_k: hits[:top_k])
    @patch("RAG.retriever.embed_query", return_value=[0.1, 0.2])
    @patch("RAG.retriever.get_collection")
    def test_retrieval_separates_shared_docs_from_customer_history(
        self, get_collection, _embed_query, _rerank
    ):
        collection = Mock()
        collection.count.return_value = 3

        def query(**kwargs):
            where = kwargs["where"]
            if where == {"category": {"$ne": "incident_history"}}:
                return {
                    "documents": [["shared knowledge"]],
                    "metadatas": [[{"category": "policies", "source": "policy.md"}]],
                    "distances": [[0.1]],
                }
            self.assertEqual(
                where,
                {"$and": [{"category": "incident_history"}, {"customer": "tenant-a"}]},
            )
            return {
                "documents": [["tenant case"]],
                "metadatas": [[{"category": "incident_history", "customer": "tenant-a"}]],
                "distances": [[0.2]],
            }

        collection.query.side_effect = query
        get_collection.return_value = collection

        hits = retrieve("suspicious login", customer="tenant-a")

        self.assertEqual([hit["text"] for hit in hits], ["shared knowledge", "tenant case"])
        self.assertEqual(collection.query.call_count, 2)

    def test_retrieval_rejects_missing_customer_before_search(self):
        with self.assertRaisesRegex(ValueError, "customer"):
            retrieve("suspicious login", customer="")


if __name__ == "__main__":
    unittest.main()
