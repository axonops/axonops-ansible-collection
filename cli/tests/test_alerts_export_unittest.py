import unittest

from axonopscli.components.alerts import SecretRedactor, REDACTED


class TestSecretRedactor(unittest.TestCase):

    def test_redacts_slack_webhook_url(self):
        payload = {
            "Type": "slack",
            "Params": {"name": "ops", "webhook_url": "https://hooks.slack.com/services/SECRET"},
        }
        result = SecretRedactor.redact(payload)
        self.assertEqual(result["Params"]["webhook_url"], REDACTED)
        self.assertEqual(result["Params"]["name"], "ops")  # non-secret untouched
        self.assertEqual(result["Type"], "slack")

    def test_redacts_pagerduty_service_key(self):
        payload = {"Type": "pagerduty", "Params": {"service_key": "abc123"}}
        result = SecretRedactor.redact(payload)
        self.assertEqual(result["Params"]["service_key"], REDACTED)

    def test_redacts_opsgenie_api_key(self):
        payload = {"Type": "opsgenie", "Params": {"api_key": "key-xyz"}}
        result = SecretRedactor.redact(payload)
        self.assertEqual(result["Params"]["api_key"], REDACTED)

    def test_redacts_servicenow_password(self):
        payload = {
            "Type": "servicenow",
            "Params": {"username": "svc", "password": "p@ss", "instance_url": "https://x.service-now.com"},
        }
        result = SecretRedactor.redact(payload)
        self.assertEqual(result["Params"]["password"], REDACTED)
        self.assertEqual(result["Params"]["username"], "svc")  # username intentionally not redacted
        self.assertEqual(result["Params"]["instance_url"], "https://x.service-now.com")  # not in patterns

    def test_redacts_nested_definitions_list_preserves_structure(self):
        payload = {
            "Definitions": [
                {"Type": "slack", "Params": {"webhook_url": "u1"}},
                {"Type": "pagerduty", "Params": {"service_key": "k1"}},
            ],
            "Routing": [{"severity": "error", "integration_name": "ops"}],
        }
        result = SecretRedactor.redact(payload)
        self.assertEqual(result["Definitions"][0]["Params"]["webhook_url"], REDACTED)
        self.assertEqual(result["Definitions"][1]["Params"]["service_key"], REDACTED)
        self.assertEqual(result["Routing"], payload["Routing"])  # untouched
        self.assertEqual(len(result["Definitions"]), 2)

    def test_non_secret_fields_untouched(self):
        payload = {
            "name": "rule1",
            "severity": "warning",
            "duration": "5m",
            "description": "Not a secret",
        }
        result = SecretRedactor.redact(payload)
        self.assertEqual(result, payload)

    def test_input_is_not_mutated(self):
        payload = {"Params": {"webhook_url": "https://example.com"}}
        SecretRedactor.redact(payload)
        self.assertEqual(payload["Params"]["webhook_url"], "https://example.com")


if __name__ == "__main__":
    unittest.main()
