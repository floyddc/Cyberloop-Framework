import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from RAG.api import app


class RagApiTests(unittest.TestCase):
    def test_health_is_unavailable_before_models_are_loaded(self):
        with patch("RAG.api._models_ready", False):
            response = TestClient(app).get("/health")

        self.assertEqual(response.status_code, 503)

    def test_health_is_available_after_startup_models_are_loaded(self):
        with patch("RAG.api._warm_models"), TestClient(app) as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch("RAG.api.RetrieveAgent")
    def test_retrieve_delegates_to_retrieve_agent(self, retrieve_agent_class):
        retrieve_agent_class.return_value.retrieve.return_value = [
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
        ]

        with patch("RAG.api._warm_models"), TestClient(app) as client:
            response = client.post(
                "/retrieve",
                json={
                    "customer": 123,
                    "query": "suspicious activity",
                    "k_cases": 2,
                    "k_kb": 1,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)
        retrieve_agent_class.return_value.retrieve.assert_called_once_with(
            "suspicious activity",
            customer_id=123,
            k_cases=2,
            k_kb=1,
        )

    @patch("RAG.api.RetrieveAgent")
    def test_retrieve_passes_structured_alert_to_retrieve_agent(self, retrieve_agent_class):
        alert = {
            "alert_title": "Suspicious email with malicious attachment",
            "alert_customer_id": 123,
            "alert_iocs": [{"ioc_description": "Macro-enabled malicious document"}],
        }
        retrieve_agent_class.return_value.retrieve.return_value = []

        with patch("RAG.api._warm_models"), TestClient(app) as client:
            response = client.post(
                "/retrieve",
                json={
                    "customer": 123,
                    "alert": alert,
                    "k_cases": 0,
                    "k_kb": 10,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
        retrieve_agent_class.return_value.retrieve.assert_called_once_with(
            alert,
            customer_id=123,
            k_cases=0,
            k_kb=10,
        )

    @patch("RAG.api.replace_source_records")
    @patch("RAG.api.IncidentHistoryStore")
    def test_index_cases_upserts_and_returns_database_ids(self, store_class, replace):
        store_class.return_value.upsert_case.return_value = 42

        with patch("RAG.api._warm_models"), TestClient(app) as client:
            response = client.post(
                "/index/cases",
                json={
                    "cases": [{
                        "customer": 123,
                        "title": "Previous case",
                        "text": "Endpoint isolated",
                    }]
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"indexed": 1, "ids": [42]})
        store_class.return_value.upsert_case.assert_called_once_with(
            None, 123, "Previous case", "Endpoint isolated"
        )
        replace.assert_called_once()
        records = replace.call_args.args[1]
        self.assertEqual(records[0]["metadata"]["customer"], 123)
        self.assertEqual(records[0]["metadata"]["record_id"], 42)

    @patch("RAG.api.replace_source_records")
    @patch("RAG.api.IncidentHistoryStore")
    def test_delete_case_removes_database_and_vector_records(self, store_class, replace):
        store_class.return_value.delete_case.return_value = True

        with patch("RAG.api._warm_models"), TestClient(app) as client:
            response = client.delete("/index/cases/42")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"deleted": True, "id": 42})
        store_class.return_value.delete_case.assert_called_once_with(42)
        replace.assert_called_once_with("incident_history::42", [])

    def test_retrieve_rejects_invalid_customer(self):
        with patch("RAG.api._warm_models"), TestClient(app) as client:
            response = client.post(
                "/retrieve",
                json={"customer": "tenant-a", "query": "suspicious activity"},
            )

        self.assertEqual(response.status_code, 422)

    def test_retrieve_rejects_alert_customer_mismatch(self):
        with patch("RAG.api._warm_models"), TestClient(app) as client:
            response = client.post(
                "/retrieve",
                json={
                    "customer": 123,
                    "alert": {"alert_customer_id": 456, "alert_title": "Suspicious email"},
                },
            )

        self.assertEqual(response.status_code, 422)

    def test_retrieve_requires_exactly_one_input(self):
        with patch("RAG.api._warm_models"), TestClient(app) as client:
            response = client.post("/retrieve", json={"customer": 123})

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
