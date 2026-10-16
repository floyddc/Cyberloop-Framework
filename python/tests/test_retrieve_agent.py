import unittest
from unittest.mock import patch

from retrieve_agent import RetrieveAgent


class RetrieveAgentTests(unittest.TestCase):
    @patch("retrieve_agent.retrieve_rag_results", return_value=[{"type": "case"}])
    def test_structured_retrieval_delegates_to_rag_pipeline(self, rag_retrieve):
        results = RetrieveAgent().retrieve_results(
            "suspicious activity", customer_id=123, k_cases=2, k_kb=1
        )

        self.assertEqual(results, [{"type": "case"}])
        rag_retrieve.assert_called_once_with(
            "suspicious activity",
            customer_id=123,
            k_cases=2,
            k_kb=1,
        )

    @patch("retrieve_agent.build_context", return_value="Relevant context")
    def test_retrieve_returns_context(self, build_context):
        result = RetrieveAgent(top_k=3).retrieve("suspicious activity", customer_id=123)

        self.assertEqual(
            result,
            {"query": "suspicious activity", "context": "Relevant context"},
        )
        build_context.assert_called_once_with(
            "suspicious activity", customer_id=123, top_k=3
        )

    def test_retrieve_rejects_invalid_customer(self):
        result = RetrieveAgent().retrieve("suspicious activity", customer_id=0)

        self.assertEqual(result["query"], "suspicious activity")
        self.assertIn("positive integer", result["error"])


if __name__ == "__main__":
    unittest.main()
