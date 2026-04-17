import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from axonopscli.components.alerts import SecretRedactor, REDACTED, AlertsExporter


def _args(org="acme", cluster="prod", exportpath="/tmp/x", include_secrets=False, v=0):
    return SimpleNamespace(
        org=org, cluster=cluster, exportpath=exportpath,
        include_secrets=include_secrets, v=v,
    )


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


class TestAlertsExporterFetch(unittest.TestCase):

    def test_fetch_calls_alert_rules_and_integrations_endpoints(self):
        axonops = MagicMock()
        axonops.do_request.side_effect = [
            {"rules": [{"name": "r1"}]},
            {"Definitions": [], "Routing": []},
        ]
        args = _args(org="acme", cluster="prod")
        exporter = AlertsExporter(axonops, args)

        exporter.fetch()

        self.assertEqual(axonops.do_request.call_count, 2)
        call_urls = [c.kwargs.get('url') or c.args[0] for c in axonops.do_request.call_args_list]
        self.assertIn("/api/v1/alert-rules/acme/cassandra/prod", call_urls)
        self.assertIn("/api/v1/integrations/acme/cassandra/prod", call_urls)
        self.assertEqual(exporter.alert_rules, {"rules": [{"name": "r1"}]})
        self.assertEqual(exporter.integrations, {"Definitions": [], "Routing": []})

    def test_fetch_normalizes_none_response_to_empty_dict(self):
        axonops = MagicMock()
        axonops.do_request.side_effect = [None, None]
        exporter = AlertsExporter(axonops, _args())

        exporter.fetch()

        self.assertEqual(exporter.alert_rules, {})
        self.assertEqual(exporter.integrations, {})


import json
import os
import stat
import tempfile


class TestAlertsExporterExport(unittest.TestCase):

    def _make_exporter(self, alert_rules, integrations, exportpath, include_secrets=False):
        exporter = AlertsExporter(MagicMock(), _args(exportpath=exportpath, include_secrets=include_secrets))
        exporter.alert_rules = alert_rules
        exporter.integrations = integrations
        return exporter

    def test_export_writes_both_files_when_both_resources_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = self._make_exporter(
                alert_rules={"rules": [{"name": "r1"}]},
                integrations={"Definitions": [{"Type": "slack", "Params": {"webhook_url": "u"}}],
                              "Routing": [], "Overrides": []},
                exportpath=tmp,
            )
            ex.export(tmp, include_secrets=False)

            self.assertTrue(os.path.exists(os.path.join(tmp, "alert_rules.json")))
            self.assertTrue(os.path.exists(os.path.join(tmp, "integrations.json")))

    def test_export_default_redacts_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = self._make_exporter(
                alert_rules={"rules": [{"name": "r1"}]},
                integrations={"Definitions": [{"Type": "slack", "Params": {"webhook_url": "real-secret"}}],
                              "Routing": [], "Overrides": []},
                exportpath=tmp,
            )
            ex.export(tmp, include_secrets=False)

            with open(os.path.join(tmp, "integrations.json")) as f:
                data = json.load(f)
            self.assertEqual(data["Definitions"][0]["Params"]["webhook_url"], REDACTED)

    def test_export_include_secrets_keeps_real_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = self._make_exporter(
                alert_rules={},
                integrations={"Definitions": [{"Type": "slack", "Params": {"webhook_url": "real-secret"}}],
                              "Routing": [], "Overrides": []},
                exportpath=tmp,
            )
            ex.export(tmp, include_secrets=True)

            with open(os.path.join(tmp, "integrations.json")) as f:
                data = json.load(f)
            self.assertEqual(data["Definitions"][0]["Params"]["webhook_url"], "real-secret")

    def test_export_files_have_mode_0600(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = self._make_exporter(
                alert_rules={"rules": [{"name": "r1"}]},
                integrations={"Definitions": [{"Type": "slack", "Params": {}}]},
                exportpath=tmp,
            )
            ex.export(tmp, include_secrets=False)

            for name in ("alert_rules.json", "integrations.json"):
                mode = stat.S_IMODE(os.stat(os.path.join(tmp, name)).st_mode)
                self.assertEqual(mode, 0o600, f"{name} mode is {oct(mode)}, expected 0o600")

    def test_export_skips_empty_alert_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = self._make_exporter(
                alert_rules={},
                integrations={"Definitions": [{"Type": "slack"}]},
                exportpath=tmp,
            )
            ex.export(tmp, include_secrets=False)

            self.assertFalse(os.path.exists(os.path.join(tmp, "alert_rules.json")))
            self.assertTrue(os.path.exists(os.path.join(tmp, "integrations.json")))

    def test_export_skips_empty_integrations(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = self._make_exporter(
                alert_rules={"rules": [{"name": "r1"}]},
                integrations={"Definitions": [], "Routing": [], "Overrides": []},
                exportpath=tmp,
            )
            ex.export(tmp, include_secrets=False)

            self.assertTrue(os.path.exists(os.path.join(tmp, "alert_rules.json")))
            self.assertFalse(os.path.exists(os.path.join(tmp, "integrations.json")))

    def test_export_writes_nothing_when_both_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = self._make_exporter(alert_rules={}, integrations={}, exportpath=tmp)
            ex.export(tmp, include_secrets=False)

            self.assertEqual(os.listdir(tmp), [])

    def test_export_creates_directory_if_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "new_subdir")
            ex = self._make_exporter(
                alert_rules={"rules": [{"name": "r1"}]},
                integrations={},
                exportpath=target,
            )
            ex.export(target, include_secrets=False)

            self.assertTrue(os.path.isdir(target))
            self.assertTrue(os.path.exists(os.path.join(target, "alert_rules.json")))

    def test_export_raises_when_path_exists_as_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            file_path = os.path.join(tmp, "file_not_dir")
            with open(file_path, 'w') as f:
                f.write("x")
            ex = self._make_exporter(
                alert_rules={"rules": [{"name": "r1"}]},
                integrations={},
                exportpath=file_path,
            )
            with self.assertRaises(NotADirectoryError):
                ex.export(file_path, include_secrets=False)


class TestAlertsExporterGitignore(unittest.TestCase):

    def _exporter_with_full_data(self, exportpath, include_secrets):
        ex = AlertsExporter(MagicMock(), _args(exportpath=exportpath, include_secrets=include_secrets))
        ex.alert_rules = {"rules": [{"name": "r1"}]}
        ex.integrations = {"Definitions": [{"Type": "slack", "Params": {"webhook_url": "u"}}],
                           "Routing": [], "Overrides": []}
        return ex

    def test_gitignore_created_with_both_filenames_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = self._exporter_with_full_data(tmp, include_secrets=True)
            ex.export(tmp, include_secrets=True)

            gitignore_path = os.path.join(tmp, ".gitignore")
            self.assertTrue(os.path.exists(gitignore_path))
            with open(gitignore_path) as f:
                lines = [line.strip() for line in f if line.strip()]
            self.assertIn("alert_rules.json", lines)
            self.assertIn("integrations.json", lines)

    def test_gitignore_appends_only_missing_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            gitignore_path = os.path.join(tmp, ".gitignore")
            with open(gitignore_path, "w") as f:
                f.write("alert_rules.json\n*.tmp\n")
            ex = self._exporter_with_full_data(tmp, include_secrets=True)
            ex.export(tmp, include_secrets=True)

            with open(gitignore_path) as f:
                lines = [line.strip() for line in f if line.strip()]
            self.assertEqual(lines.count("alert_rules.json"), 1)
            self.assertIn("integrations.json", lines)
            self.assertIn("*.tmp", lines)

    def test_gitignore_unchanged_when_both_already_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            gitignore_path = os.path.join(tmp, ".gitignore")
            original = "alert_rules.json\nintegrations.json\n"
            with open(gitignore_path, "w") as f:
                f.write(original)
            ex = self._exporter_with_full_data(tmp, include_secrets=True)
            ex.export(tmp, include_secrets=True)

            with open(gitignore_path) as f:
                self.assertEqual(f.read(), original)

    def test_gitignore_not_written_when_secrets_redacted(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = self._exporter_with_full_data(tmp, include_secrets=False)
            ex.export(tmp, include_secrets=False)

            self.assertFalse(os.path.exists(os.path.join(tmp, ".gitignore")))


class TestApplicationRunAlerts(unittest.TestCase):

    def _patch_axonops(self, alert_rules_response, integrations_response):
        """Patch AxonOps.do_request at the class level to return canned responses."""
        from axonopscli.axonops import AxonOps

        responses = {
            "/api/v1/alert-rules/acme/cassandra/prod": alert_rules_response,
            "/api/v1/integrations/acme/cassandra/prod": integrations_response,
        }

        def fake_do_request(self, url, method='GET', **kwargs):
            return responses.get(url, {})

        return patch.object(AxonOps, 'do_request', new=fake_do_request)

    def test_application_run_alerts_writes_files(self):
        from axonopscli.application import Application

        with tempfile.TemporaryDirectory() as tmp:
            with self._patch_axonops(
                alert_rules_response={"rules": [{"name": "r1"}]},
                integrations_response={"Definitions": [{"Type": "slack", "Params": {"webhook_url": "u"}}],
                                       "Routing": [], "Overrides": []},
            ):
                app = Application()
                app.run([
                    "--org", "acme",
                    "--cluster", "prod",
                    "--token", "t",
                    "alerts",
                    "--exportpath", tmp,
                ])

            self.assertTrue(os.path.exists(os.path.join(tmp, "alert_rules.json")))
            self.assertTrue(os.path.exists(os.path.join(tmp, "integrations.json")))

            with open(os.path.join(tmp, "integrations.json")) as f:
                data = json.load(f)
            self.assertEqual(data["Definitions"][0]["Params"]["webhook_url"], REDACTED)

    def test_application_run_alerts_with_include_secrets(self):
        from axonopscli.application import Application

        with tempfile.TemporaryDirectory() as tmp:
            with self._patch_axonops(
                alert_rules_response={},
                integrations_response={"Definitions": [{"Type": "slack", "Params": {"webhook_url": "u"}}],
                                       "Routing": [], "Overrides": []},
            ):
                app = Application()
                app.run([
                    "--org", "acme",
                    "--cluster", "prod",
                    "--token", "t",
                    "alerts",
                    "--exportpath", tmp,
                    "--include-secrets",
                ])

            with open(os.path.join(tmp, "integrations.json")) as f:
                data = json.load(f)
            self.assertEqual(data["Definitions"][0]["Params"]["webhook_url"], "u")

            with open(os.path.join(tmp, ".gitignore")) as f:
                gi_lines = {line.strip() for line in f if line.strip()}
            self.assertIn("integrations.json", gi_lines)


if __name__ == "__main__":
    unittest.main()
