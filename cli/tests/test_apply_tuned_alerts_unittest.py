import io
import contextlib
import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock


def _args(
    org="acme",
    cluster="bc1",
    cluster_type="cassandra",
    input="/tmp/x.json",
    dry_run=False,
    yes=True,  # default True in tests so we don't hang on prompt
    continue_on_error=False,
    allow_redacted=False,
    v=0,
):
    return SimpleNamespace(
        org=org,
        cluster=cluster,
        cluster_type=cluster_type,
        input=input,
        dry_run=dry_run,
        yes=yes,
        continue_on_error=continue_on_error,
        allow_redacted=allow_redacted,
        v=v,
        # extras forwarded by AxonOps but unused here
        url=None,
        token="t",
        username=None,
        password=None,
    )


def _sample_tuned_input(cluster_name="bc1"):
    """Minimal tuned JSON with two rules — same shape as tune_alerts output."""
    return {
        "name": cluster_name,
        "metricrules": [
            {
                "id": "rule-1",
                "correlationId": "corr-1",
                "alert": "GC duration",
                "expr": "jvm_gc_CollectionTime >= 1087.91",
                "for": "2m",
                "operator": ">=",
                "criticalValue": 1186.81,
                "warningValue": 1087.91,
                "filters": [],
                "annotations": {},
                "integrations": {},
            },
            {
                "id": "rule-2",
                "correlationId": "corr-2",
                "alert": "NTP offset",
                "expr": "abs(host_ntp_offset_seconds) * 1000 >= 200",
                "for": "5m",
                "operator": ">=",
                "criticalValue": 250,
                "warningValue": 200,
                "filters": [],
                "annotations": {},
                "integrations": {},
            },
        ],
    }


class TestContainsRedacted(unittest.TestCase):
    """Detect the REDACTED sentinel recursively in a tuned-alerts JSON."""

    def test_flat_top_level_redacted_value_detected(self):
        from axonopscli.components.apply_tuned_alerts import contains_redacted
        self.assertTrue(contains_redacted({"foo": "***REDACTED***"}))

    def test_deeply_nested_redacted_detected(self):
        from axonopscli.components.apply_tuned_alerts import contains_redacted
        payload = {"metricrules": [{"integrations": {"webhook_url": "***REDACTED***"}}]}
        self.assertTrue(contains_redacted(payload))

    def test_no_redacted_returns_false(self):
        from axonopscli.components.apply_tuned_alerts import contains_redacted
        payload = _sample_tuned_input()
        self.assertFalse(contains_redacted(payload))

    def test_similar_but_not_exact_not_detected(self):
        """Must match the exact sentinel string, not a substring."""
        from axonopscli.components.apply_tuned_alerts import contains_redacted
        self.assertFalse(contains_redacted({"x": "REDACTED"}))
        self.assertFalse(contains_redacted({"x": "Contains ***REDACTED*** inside"}))


class TestLoadInput(unittest.TestCase):

    def test_loads_valid_tuned_json(self):
        from axonopscli.components.apply_tuned_alerts import AlertsApplier
        applier = AlertsApplier(MagicMock(), _args())
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "t.json")
            with open(path, "w") as f:
                json.dump(_sample_tuned_input(), f)
            data = applier.load_input(path)
        self.assertEqual(data["name"], "bc1")
        self.assertEqual(len(data["metricrules"]), 2)

    def test_load_raises_for_missing_metricrules(self):
        from axonopscli.components.apply_tuned_alerts import AlertsApplier
        applier = AlertsApplier(MagicMock(), _args())
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "t.json")
            with open(path, "w") as f:
                json.dump({"name": "bc1"}, f)
            with self.assertRaises(ValueError):
                applier.load_input(path)

    def test_load_raises_for_non_object_top_level(self):
        from axonopscli.components.apply_tuned_alerts import AlertsApplier
        applier = AlertsApplier(MagicMock(), _args())
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "t.json")
            with open(path, "w") as f:
                f.write("[]")
            with self.assertRaises(ValueError):
                applier.load_input(path)

    def test_load_raises_for_malformed_json(self):
        from axonopscli.components.apply_tuned_alerts import AlertsApplier
        applier = AlertsApplier(MagicMock(), _args())
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "t.json")
            with open(path, "w") as f:
                f.write("{not json")
            with self.assertRaises(ValueError):
                applier.load_input(path)


class TestApplyHappyPath(unittest.TestCase):

    def test_posts_each_rule_to_correct_url_with_correct_payload(self):
        from axonopscli.components.apply_tuned_alerts import AlertsApplier
        axonops = MagicMock()
        axonops.get_cluster_type.return_value = "cassandra"
        axonops.do_request.return_value = {}
        applier = AlertsApplier(axonops, _args(org="burodecredito", cluster="bc1"))

        result = applier.apply(
            _sample_tuned_input(), dry_run=False, continue_on_error=False,
            allow_redacted=False,
        )
        self.assertEqual(len(result.applied), 2)
        self.assertEqual(len(result.failed), 0)
        self.assertEqual(len(result.skipped), 0)
        self.assertFalse(result.dry_run)

        # Two POSTs were made with the right URL and one rule per call
        self.assertEqual(axonops.do_request.call_count, 2)
        for call, expected_rule in zip(
            axonops.do_request.call_args_list,
            _sample_tuned_input()["metricrules"],
        ):
            url = call.kwargs.get('url') or call.args[0]
            method = call.kwargs.get('method') or (call.args[1] if len(call.args) > 1 else None)
            json_data = call.kwargs.get('json_data')
            self.assertEqual(
                url,
                "/api/v1/alert-rules/burodecredito/cassandra/bc1",
            )
            self.assertEqual(method, "POST")
            self.assertEqual(json_data["id"], expected_rule["id"])
            self.assertEqual(json_data["alert"], expected_rule["alert"])


class TestApplyDryRun(unittest.TestCase):

    def test_dry_run_makes_zero_http_calls(self):
        from axonopscli.components.apply_tuned_alerts import AlertsApplier
        axonops = MagicMock()
        axonops.get_cluster_type.return_value = "cassandra"
        applier = AlertsApplier(axonops, _args(dry_run=True))

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            result = applier.apply(
                _sample_tuned_input(), dry_run=True, continue_on_error=False,
                allow_redacted=False,
            )
        self.assertEqual(axonops.do_request.call_count, 0)
        self.assertTrue(result.dry_run)
        self.assertEqual(len(result.applied), 2)
        out = buf.getvalue()
        self.assertIn("[dry-run]", out)
        self.assertIn("/api/v1/alert-rules/acme/cassandra/bc1", out)


class TestRedactedDetection(unittest.TestCase):

    def test_refuses_to_apply_redacted_input_without_allow_flag(self):
        from axonopscli.components.apply_tuned_alerts import (
            AlertsApplier, RedactedInputError,
        )
        data = _sample_tuned_input()
        data["metricrules"][0]["integrations"] = {"webhook_url": "***REDACTED***"}
        axonops = MagicMock()
        axonops.get_cluster_type.return_value = "cassandra"
        applier = AlertsApplier(axonops, _args(allow_redacted=False))
        with self.assertRaises(RedactedInputError):
            applier.apply(data, dry_run=False, continue_on_error=False,
                          allow_redacted=False)
        self.assertEqual(axonops.do_request.call_count, 0)

    def test_allows_redacted_input_with_allow_flag(self):
        from axonopscli.components.apply_tuned_alerts import AlertsApplier
        data = _sample_tuned_input()
        data["metricrules"][0]["integrations"] = {"webhook_url": "***REDACTED***"}
        axonops = MagicMock()
        axonops.get_cluster_type.return_value = "cassandra"
        axonops.do_request.return_value = {}
        applier = AlertsApplier(axonops, _args(allow_redacted=True))
        result = applier.apply(data, dry_run=False, continue_on_error=False,
                               allow_redacted=True)
        self.assertEqual(len(result.applied), 2)


class TestRuleValidation(unittest.TestCase):

    def test_rule_without_id_is_skipped(self):
        from axonopscli.components.apply_tuned_alerts import AlertsApplier
        axonops = MagicMock()
        axonops.get_cluster_type.return_value = "cassandra"
        axonops.do_request.return_value = {}
        data = _sample_tuned_input()
        del data["metricrules"][0]["id"]
        applier = AlertsApplier(axonops, _args())
        result = applier.apply(data, dry_run=False, continue_on_error=True,
                               allow_redacted=False)
        # Only rule-2 applied; rule-1 skipped
        self.assertEqual(len(result.applied), 1)
        self.assertEqual(len(result.skipped), 1)
        self.assertIn("id", result.skipped[0][1].lower())
        self.assertEqual(axonops.do_request.call_count, 1)

    def test_rule_missing_required_field_is_skipped(self):
        from axonopscli.components.apply_tuned_alerts import AlertsApplier
        axonops = MagicMock()
        axonops.get_cluster_type.return_value = "cassandra"
        axonops.do_request.return_value = {}
        data = _sample_tuned_input()
        del data["metricrules"][0]["alert"]
        applier = AlertsApplier(axonops, _args())
        result = applier.apply(data, dry_run=False, continue_on_error=True,
                               allow_redacted=False)
        self.assertEqual(len(result.applied), 1)
        self.assertEqual(len(result.skipped), 1)


class TestPerRuleErrorHandling(unittest.TestCase):

    def test_default_stops_on_first_failure(self):
        from axonopscli.components.apply_tuned_alerts import AlertsApplier
        from axonopscli.utils import HTTPCodeError
        axonops = MagicMock()
        axonops.get_cluster_type.return_value = "cassandra"
        # First call raises, second should never be made
        axonops.do_request.side_effect = HTTPCodeError("500 server error")
        applier = AlertsApplier(axonops, _args())
        with self.assertRaises(HTTPCodeError):
            applier.apply(_sample_tuned_input(), dry_run=False,
                          continue_on_error=False, allow_redacted=False)
        self.assertEqual(axonops.do_request.call_count, 1)

    def test_continue_on_error_processes_all_rules(self):
        from axonopscli.components.apply_tuned_alerts import AlertsApplier
        from axonopscli.utils import HTTPCodeError
        axonops = MagicMock()
        axonops.get_cluster_type.return_value = "cassandra"
        # First call fails, second succeeds
        axonops.do_request.side_effect = [
            HTTPCodeError("500 server error"),
            {},
        ]
        applier = AlertsApplier(axonops, _args())
        result = applier.apply(
            _sample_tuned_input(), dry_run=False, continue_on_error=True,
            allow_redacted=False,
        )
        self.assertEqual(len(result.applied), 1)
        self.assertEqual(len(result.failed), 1)
        self.assertEqual(axonops.do_request.call_count, 2)
        self.assertIn("500", result.failed[0][1])


class TestPrintSummary(unittest.TestCase):

    def test_summary_shows_applied_failed_skipped(self):
        from axonopscli.components.apply_tuned_alerts import (
            AlertsApplier, ApplyResult,
        )
        applier = AlertsApplier(MagicMock(), _args())
        result = ApplyResult(
            applied=["GC duration", "NTP offset"],
            failed=[("Some Rule", "500 error")],
            skipped=[("Bad Rule", "missing id")],
            dry_run=False,
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            applier.print_summary(result)
        out = buf.getvalue()
        self.assertIn("Applied 2", out)
        self.assertIn("failed 1", out)
        self.assertIn("skipped 1", out)

    def test_summary_dry_run_line(self):
        from axonopscli.components.apply_tuned_alerts import (
            AlertsApplier, ApplyResult,
        )
        applier = AlertsApplier(MagicMock(), _args())
        result = ApplyResult(
            applied=["GC duration", "NTP offset"],
            failed=[],
            skipped=[],
            dry_run=True,
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            applier.print_summary(result)
        out = buf.getvalue()
        self.assertIn("[dry-run]", out)
        self.assertIn("Would apply 2 rules", out)


class TestApplicationRunApplyTunedAlerts(unittest.TestCase):
    """End-to-end via Application.run()."""

    def test_end_to_end_with_yes_skips_prompt_and_posts(self):
        from axonopscli.application import Application
        from axonopscli.axonops import AxonOps

        with tempfile.TemporaryDirectory() as tmp:
            input_path = os.path.join(tmp, "alert_rules.tuned.for.bc1.json")
            with open(input_path, "w") as f:
                json.dump(_sample_tuned_input(), f)

            with patch.object(AxonOps, 'do_request', return_value={}) as do_req:
                Application().run([
                    "--org", "burodecredito", "--cluster", "bc1", "--token", "t",
                    "apply-tuned-alerts", "--input", input_path, "--yes",
                ])

            # Two POSTs
            self.assertEqual(do_req.call_count, 2)
            for call in do_req.call_args_list:
                url = call.kwargs.get('url') or call.args[0]
                method = call.kwargs.get('method') or (call.args[1] if len(call.args) > 1 else None)
                self.assertEqual(
                    url,
                    "/api/v1/alert-rules/burodecredito/cassandra/bc1",
                )
                self.assertEqual(method, "POST")

    def test_end_to_end_dry_run_makes_no_http_calls(self):
        from axonopscli.application import Application
        from axonopscli.axonops import AxonOps

        with tempfile.TemporaryDirectory() as tmp:
            input_path = os.path.join(tmp, "alert_rules.tuned.for.bc1.json")
            with open(input_path, "w") as f:
                json.dump(_sample_tuned_input(), f)

            buf = io.StringIO()
            with patch.object(AxonOps, 'do_request', return_value={}) as do_req, \
                    contextlib.redirect_stdout(buf):
                Application().run([
                    "--org", "burodecredito", "--cluster", "bc1", "--token", "t",
                    "apply-tuned-alerts", "--input", input_path, "--dry-run",
                ])
            self.assertEqual(do_req.call_count, 0)
            self.assertIn("[dry-run]", buf.getvalue())

    def test_prompt_refusal_exits_130(self):
        """Prompt response "n" aborts with exit code 130."""
        from axonopscli.application import Application
        from axonopscli.axonops import AxonOps

        with tempfile.TemporaryDirectory() as tmp:
            input_path = os.path.join(tmp, "alert_rules.tuned.for.bc1.json")
            with open(input_path, "w") as f:
                json.dump(_sample_tuned_input(), f)

            with patch.object(AxonOps, 'do_request', return_value={}) as do_req, \
                    patch('sys.stdin') as fake_stdin, \
                    patch('builtins.input', return_value="n"):
                fake_stdin.isatty.return_value = True
                with self.assertRaises(SystemExit) as ctx:
                    Application().run([
                        "--org", "burodecredito", "--cluster", "bc1", "--token", "t",
                        "apply-tuned-alerts", "--input", input_path,
                    ])
                self.assertEqual(ctx.exception.code, 130)
                self.assertEqual(do_req.call_count, 0)

    def test_non_tty_stdin_without_yes_errors_out(self):
        from axonopscli.application import Application
        from axonopscli.axonops import AxonOps

        with tempfile.TemporaryDirectory() as tmp:
            input_path = os.path.join(tmp, "alert_rules.tuned.for.bc1.json")
            with open(input_path, "w") as f:
                json.dump(_sample_tuned_input(), f)

            with patch.object(AxonOps, 'do_request', return_value={}) as do_req, \
                    patch('sys.stdin') as fake_stdin:
                fake_stdin.isatty.return_value = False
                with self.assertRaises(SystemExit) as ctx:
                    Application().run([
                        "--org", "burodecredito", "--cluster", "bc1", "--token", "t",
                        "apply-tuned-alerts", "--input", input_path,
                    ])
                # Non-zero exit; no POSTs.
                self.assertNotEqual(ctx.exception.code, 0)
                self.assertEqual(do_req.call_count, 0)

    def test_continue_on_error_flag_exits_nonzero_when_any_failed(self):
        from axonopscli.application import Application
        from axonopscli.axonops import AxonOps
        from axonopscli.utils import HTTPCodeError

        with tempfile.TemporaryDirectory() as tmp:
            input_path = os.path.join(tmp, "alert_rules.tuned.for.bc1.json")
            with open(input_path, "w") as f:
                json.dump(_sample_tuned_input(), f)

            calls = []

            def fake_do_request(self, url, method='GET', **kwargs):
                calls.append((url, method))
                if len(calls) == 1:
                    raise HTTPCodeError("500 server error")
                return {}

            with patch.object(AxonOps, 'do_request', new=fake_do_request):
                with self.assertRaises(SystemExit) as ctx:
                    Application().run([
                        "--org", "burodecredito", "--cluster", "bc1", "--token", "t",
                        "apply-tuned-alerts", "--input", input_path,
                        "--yes", "--continue-on-error",
                    ])
                self.assertNotEqual(ctx.exception.code, 0)
                # Both rules attempted despite the first failure
                self.assertEqual(len(calls), 2)

    def test_redacted_input_refuses_without_allow_flag(self):
        from axonopscli.application import Application
        from axonopscli.axonops import AxonOps

        with tempfile.TemporaryDirectory() as tmp:
            input_path = os.path.join(tmp, "alert_rules.tuned.for.bc1.json")
            data = _sample_tuned_input()
            data["metricrules"][0]["integrations"] = {"webhook_url": "***REDACTED***"}
            with open(input_path, "w") as f:
                json.dump(data, f)

            with patch.object(AxonOps, 'do_request', return_value={}) as do_req:
                with self.assertRaises(SystemExit) as ctx:
                    Application().run([
                        "--org", "burodecredito", "--cluster", "bc1", "--token", "t",
                        "apply-tuned-alerts", "--input", input_path, "--yes",
                    ])
                self.assertNotEqual(ctx.exception.code, 0)
                self.assertEqual(do_req.call_count, 0)


if __name__ == "__main__":
    unittest.main()
