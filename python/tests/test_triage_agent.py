import json
import unittest
from unittest.mock import Mock, patch

from MAPE.triage_agent import TriageAgent


class TriageAgentTests(unittest.TestCase):
    def test_triage_fetches_context_and_excludes_tenant_metadata_from_prompt(self):
        client = Mock()
        client.chat.return_value = {
            "message": {
                "content": json.dumps(
                    {
                        "summary": "Suspicious login",
                        "description": "Failed login attempts",
                        "category": "credential access",
                        "severity": "medium",
                    }
                )
            }
        }
        agent = TriageAgent(client=client)
        alert = {
            "customer": "tenant-a",
            "_source": "EDR",
            "external_id": "alert-17",
            "host": "endpoint-1",
        }

        with patch("MAPE.triage_agent.retrieve_context", return_value="Relevant case history"):
            result = agent.triage(alert)

        self.assertEqual(result["severity"], "medium")
        messages = client.chat.call_args.kwargs["messages"]
        user_prompt = messages[1]["content"]
        self.assertIn('"host": "endpoint-1"', user_prompt)
        self.assertIn("Relevant case history", user_prompt)
        self.assertNotIn("tenant-a", user_prompt)
        self.assertNotIn("alert-17", user_prompt)
        self.assertNotIn("EDR", user_prompt)

    def test_triage_rejects_non_object_alert(self):
        agent = TriageAgent(client=Mock())

        with self.assertRaisesRegex(ValueError, "JSON object"):
            agent.triage([])


if __name__ == "__main__":
    unittest.main()
