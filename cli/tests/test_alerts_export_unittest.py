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
        # Actual ServiceNow API response fields: instance_name, user, password.
        payload = {
            "Type": "servicenow",
            "Params": {"user": "svc", "password": "p@ss", "instance_name": "my-instance"},
        }
        result = SecretRedactor.redact(payload)
        self.assertEqual(result["Params"]["password"], REDACTED)
        self.assertEqual(result["Params"]["user"], "svc")             # not in patterns
        self.assertEqual(result["Params"]["instance_name"], "my-instance")  # not in patterns

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

    def test_redacts_slack_api_field_url(self):
        # Slack API stores the webhook under 'url', not 'webhook_url'.
        payload = {"Type": "slack", "Params": {"name": "ops", "url": "https://hooks.slack.com/X"}}
        result = SecretRedactor.redact(payload)
        self.assertEqual(result["Params"]["url"], REDACTED)
        self.assertEqual(result["Params"]["name"], "ops")

    def test_redacts_teams_api_field_webHookURL_camelcase(self):
        # Teams API uses camelCase 'webHookURL'.
        payload = {"Type": "teams", "Params": {"webHookURL": "https://outlook.office.com/X"}}
        result = SecretRedactor.redact(payload)
        self.assertEqual(result["Params"]["webHookURL"], REDACTED)

    def test_redacts_opsgenie_key_api_field(self):
        # Opsgenie API stores the key under 'opsgenie_key', not 'api_key'.
        payload = {"Type": "opsgenie", "Params": {"opsgenie_key": "real-secret"}}
        result = SecretRedactor.redact(payload)
        self.assertEqual(result["Params"]["opsgenie_key"], REDACTED)

    def test_redacts_oauth_access_token(self):
        payload = {"Params": {"access_token": "xoxb-real-slack-bot-token"}}
        result = SecretRedactor.redact(payload)
        self.assertEqual(result["Params"]["access_token"], REDACTED)

    def test_redacts_oauth_client_secret(self):
        payload = {"Params": {"client_secret": "abc"}}
        result = SecretRedactor.redact(payload)
        self.assertEqual(result["Params"]["client_secret"], REDACTED)

    def test_redacts_bearer_token(self):
        payload = {"Params": {"bearer_token": "eyJhbGciOiJ..."}}
        result = SecretRedactor.redact(payload)
        self.assertEqual(result["Params"]["bearer_token"], REDACTED)

    def test_redacts_refresh_token(self):
        payload = {"Params": {"refresh_token": "rf-xxx"}}
        result = SecretRedactor.redact(payload)
        self.assertEqual(result["Params"]["refresh_token"], REDACTED)

    def test_redacts_credentials_field(self):
        payload = {"Params": {"credentials": "user:pass"}}
        result = SecretRedactor.redact(payload)
        self.assertEqual(result["Params"]["credentials"], REDACTED)

    def test_redaction_is_case_insensitive(self):
        payload = {"Params": {"WEBHOOK_URL": "X", "Webhook_URL": "Y", "WebHookURL": "Z"}}
        result = SecretRedactor.redact(payload)
        self.assertEqual(result["Params"]["WEBHOOK_URL"], REDACTED)
        self.assertEqual(result["Params"]["Webhook_URL"], REDACTED)
        self.assertEqual(result["Params"]["WebHookURL"], REDACTED)

    def test_non_secret_url_variants_are_not_over_redacted(self):
        # These fields are non-secret metadata that appear in integration
        # responses. They must not be redacted.
        # Note: any field ending in _url IS redacted (e.g. axonops_url) on
        # purpose — false positives (over-redaction of non-secrets) are
        # acceptable; false negatives (leaked secrets) are not.
        payload = {
            "Params": {
                "name": "ops",
                "instance_name": "my-instance",
                "user": "svc",
                "axondashUrl": "https://dash.axonops.cloud/acme",  # camelCase, no _url suffix
            }
        }
        result = SecretRedactor.redact(payload)
        self.assertEqual(result["Params"]["name"], "ops")
        self.assertEqual(result["Params"]["instance_name"], "my-instance")
        self.assertEqual(result["Params"]["user"], "svc")
        self.assertEqual(result["Params"]["axondashUrl"], "https://dash.axonops.cloud/acme")


class TestAlertsExporterFetch(unittest.TestCase):

    def test_fetch_calls_alert_rules_and_integrations_endpoints(self):
        axonops = MagicMock()
        axonops.get_cluster_type.return_value = "cassandra"
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
        axonops.get_cluster_type.return_value = "cassandra"
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
                integrations={"Definitions": [{"Type": "slack", "Params": {"webhook_url": "https://hooks.slack.com/SENTINEL-SECRET"}}],
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

    def test_export_tightens_mode_when_overwriting_world_readable_file(self):
        # If an earlier run (or the user) left a world-readable file, the
        # next export must end up 0600 regardless. Guards against the
        # chmod-after-write race.
        with tempfile.TemporaryDirectory() as tmp:
            pre_existing = os.path.join(tmp, "alert_rules.json")
            with open(pre_existing, "w") as f:
                f.write("{}")
            os.chmod(pre_existing, 0o644)  # simulate world-readable

            ex = self._make_exporter(
                alert_rules={"rules": [{"name": "r1"}]},
                integrations={},
                exportpath=tmp,
            )
            ex.export(tmp, include_secrets=False)

            mode = stat.S_IMODE(os.stat(pre_existing).st_mode)
            self.assertEqual(mode, 0o600)

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
        ex.integrations = {"Definitions": [{"Type": "slack", "Params": {"webhook_url": "https://hooks.slack.com/SENTINEL-SECRET"}}],
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
                integrations_response={"Definitions": [{"Type": "slack", "Params": {"webhook_url": "https://hooks.slack.com/SENTINEL-SECRET"}}],
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
                integrations_response={"Definitions": [{"Type": "slack", "Params": {"webhook_url": "https://hooks.slack.com/SENTINEL-SECRET"}}],
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
            self.assertEqual(
                data["Definitions"][0]["Params"]["webhook_url"],
                "https://hooks.slack.com/SENTINEL-SECRET",
            )

            with open(os.path.join(tmp, ".gitignore")) as f:
                gi_lines = {line.strip() for line in f if line.strip()}
            self.assertIn("integrations.json", gi_lines)


class TestClusterTypeFix(unittest.TestCase):

    def test_application_passes_cluster_type_default_cassandra(self):
        from axonopscli.axonops import AxonOps
        from axonopscli.application import Application

        captured = {}
        original_init = AxonOps.__init__

        def capturing_init(self, *args, **kwargs):
            captured['cluster_type'] = kwargs.get('cluster_type')
            original_init(self, *args, **kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(AxonOps, '__init__', new=capturing_init), \
                 patch.object(AxonOps, 'do_request', return_value={}):
                Application().run([
                    "--org", "acme", "--cluster", "prod", "--token", "t",
                    "alerts", "--exportpath", tmp,
                ])

        self.assertEqual(captured['cluster_type'], 'cassandra')

    def test_application_passes_cluster_type_when_overridden(self):
        from axonopscli.axonops import AxonOps
        from axonopscli.application import Application

        captured = {}
        original_init = AxonOps.__init__

        def capturing_init(self, *args, **kwargs):
            captured['cluster_type'] = kwargs.get('cluster_type')
            original_init(self, *args, **kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(AxonOps, '__init__', new=capturing_init), \
                 patch.object(AxonOps, 'do_request', return_value={}):
                Application().run([
                    "--org", "acme", "--cluster", "prod", "--cluster-type", "kafka",
                    "--token", "t",
                    "alerts", "--exportpath", tmp,
                ])

        self.assertEqual(captured['cluster_type'], 'kafka')

    def test_fetch_uses_cluster_type_in_url_for_kafka(self):
        # The cluster_type fix must flow through to the alert-rules and
        # integrations URLs, not just the AxonOps constructor.
        axonops = MagicMock()
        axonops.get_cluster_type.return_value = "kafka"
        axonops.do_request.return_value = {}
        args = _args(org="acme", cluster="prod")

        exporter = AlertsExporter(axonops, args)
        exporter.fetch()

        call_urls = [c.kwargs.get('url') or c.args[0] for c in axonops.do_request.call_args_list]
        self.assertIn("/api/v1/alert-rules/acme/kafka/prod", call_urls)
        self.assertIn("/api/v1/integrations/acme/kafka/prod", call_urls)


class TestDashboardClusterTypeInPayload(unittest.TestCase):
    """Regression guard: dashboard PUT payloads must carry the actual
    cluster_type, not a hardcoded 'cassandra'."""

    def _make_dashboard(self, cluster_type):
        from axonopscli.components.dashboard import Dashboard
        axonops = MagicMock()
        axonops.get_cluster_type.return_value = cluster_type
        args = SimpleNamespace(org="acme", cluster="prod", v=0)
        d = Dashboard(axonops, args)
        d.dashboard_data = [{"name": "existing"}]
        return d, axonops

    def test_import_dashboard_put_payload_uses_cluster_type(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Prepare a minimal dashboard json to import
            import_path = os.path.join(tmp, "new.json")
            with open(import_path, "w") as f:
                json.dump({"name": "new-board"}, f)

            d, axonops = self._make_dashboard(cluster_type="kafka")
            d.import_dashboard(import_path, dashboard_name=None, position=None, overwrite=False)

            # Inspect the PUT json_data
            put_calls = [
                c for c in axonops.do_request.call_args_list
                if (c.kwargs.get('method') or (c.args[1] if len(c.args) > 1 else None)) == 'PUT'
            ]
            self.assertTrue(put_calls, "expected a PUT call")
            payload = put_calls[-1].kwargs.get('json_data')
            self.assertEqual(payload['type'], 'kafka')

    def test_delete_dashboard_put_payload_uses_cluster_type(self):
        d, axonops = self._make_dashboard(cluster_type="kafka")
        d.dashboard_data = [{"name": "target"}]

        d.delete_dashboard("target")

        put_calls = [
            c for c in axonops.do_request.call_args_list
            if (c.kwargs.get('method') or (c.args[1] if len(c.args) > 1 else None)) == 'PUT'
        ]
        self.assertTrue(put_calls, "expected a PUT call")
        payload = put_calls[-1].kwargs.get('json_data')
        self.assertEqual(payload['type'], 'kafka')


class TestVerboseArgsScrub(unittest.TestCase):
    """Verbose mode must not print raw secrets (token, password) when
    running the alerts subcommand."""

    def test_run_alerts_verbose_does_not_print_token(self):
        from axonopscli.application import Application
        from axonopscli.axonops import AxonOps
        import io
        import contextlib

        buf = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(AxonOps, 'do_request', return_value={}):
                with contextlib.redirect_stdout(buf):
                    Application().run([
                        "--org", "acme", "--cluster", "prod",
                        "--token", "SUPER-SECRET-TOKEN-VALUE",
                        "-v",
                        "alerts", "--exportpath", tmp,
                    ])

        output = buf.getvalue()
        self.assertNotIn("SUPER-SECRET-TOKEN-VALUE", output,
                         f"Token leaked to stdout in verbose mode:\n{output}")

    def test_run_alerts_verbose_does_not_print_password(self):
        from axonopscli.application import Application
        from axonopscli.axonops import AxonOps
        import io
        import contextlib

        # Bypass AxonOps.__init__ entirely to avoid the pre-existing do_login
        # AttributeError that triggers on the username/password auth path.
        # This test is about whether run_alerts scrubs args.password from
        # stdout, not about AxonOps construction.
        def noop_init(self, *args, **kwargs):
            self.cluster_type = kwargs.get('cluster_type', 'cassandra')

        buf = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(AxonOps, '__init__', new=noop_init), \
                 patch.object(AxonOps, 'do_request', return_value={}):
                with contextlib.redirect_stdout(buf):
                    Application().run([
                        "--org", "acme", "--cluster", "prod",
                        "--url", "https://example.com",
                        "--username", "svc",
                        "--password", "P@SSWORD-SENTINEL",
                        "-v",
                        "alerts", "--exportpath", tmp,
                    ])

        output = buf.getvalue()
        self.assertNotIn("P@SSWORD-SENTINEL", output,
                         f"Password leaked to stdout in verbose mode:\n{output}")


class TestExportBeforeFetchContract(unittest.TestCase):
    """Calling export() without fetch() must not crash with
    AttributeError; it should fall through to the 'nothing to export'
    branch."""

    def test_export_before_fetch_falls_through_to_nothing_to_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            exporter = AlertsExporter(MagicMock(), _args(exportpath=tmp))
            # Explicitly not calling fetch(); alert_rules and integrations
            # remain at their None defaults.
            exporter.export(tmp, include_secrets=False)

            # Directory should be empty — no files written, no exceptions.
            self.assertEqual(os.listdir(tmp), [])


if __name__ == "__main__":
    unittest.main()
