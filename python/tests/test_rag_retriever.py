import unittest
from unittest.mock import Mock, patch

from RAG.retriever import retrieve_results


class StructuredRetrieverTests(unittest.TestCase):
    @patch("RAG.retriever.rerank")
    @patch("RAG.retriever.embed_query", return_value=[0.1, 0.2])
    @patch("RAG.retriever.get_collection")
    def test_retrieves_customer_cases_and_shared_knowledge(
        self, get_collection, _embed_query, rerank
    ):
        collection = Mock()
        collection.count.return_value = 4
        collection.query.side_effect = [
            {
                "ids": [["incident_history::8::0"]],
                "documents": [["summary: Previous case"]],
                "metadatas": [[{
                    "source": "incident_history::8",
                    "record_id": 8,
                    "customer": 123,
                    "title": "Previous case",
                }]],
            },
            {
                "ids": [["policy.md::0"]],
                "documents": [["Shared response guidance"]],
                "metadatas": [[{
                    "source": "policy.md",
                    "title": "Response policy",
                }]],
            },
        ]
        get_collection.return_value = collection
        rerank.side_effect = lambda query, hits, top_k: [
            {**hit, "rerank_score": 0.9} for hit in hits
        ]

        results = retrieve_results(
            "suspicious activity", customer_id=123, k_cases=2, k_kb=1
        )

        self.assertEqual(
            results,
            [
                {
                    "type": "case",
                    "id": 8,
                    "title": "Previous case",
                    "text": "summary: Previous case",
                    "score": 0.9,
                },
                {
                    "type": "kb",
                    "id": "policy.md",
                    "title": "Response policy",
                    "text": "Shared response guidance",
                    "score": 0.9,
                },
            ],
        )
        self.assertEqual(collection.query.call_args_list[0].kwargs["where"], {
            "$and": [{"category": "incident_history"}, {"customer": 123}]
        })
        self.assertEqual(collection.query.call_args_list[1].kwargs["where"], {
            "category": {"$ne": "incident_history"}
        })

    @patch("RAG.retriever.embed_query")
    @patch("RAG.retriever.get_collection")
    def test_skips_retrieval_when_both_limits_are_zero(self, get_collection, embed_query):
        results = retrieve_results(
            "suspicious activity", customer_id=123, k_cases=0, k_kb=0
        )

        self.assertEqual(results, [])
        get_collection.assert_not_called()
        embed_query.assert_not_called()


if __name__ == "__main__":
    unittest.main()
