import unittest

from axonopscli.components.tune_alerts import ThresholdCalculator, TuneResult


class TestThresholdCalculator(unittest.TestCase):

    def test_p99_with_20pct_headroom_for_ge_operator(self):
        # Generate 1000 samples from 0..999. Linear-interpolation p99 = 989.01
        # (positional index pos = (n-1)*p/100 = 999*0.99 = 989.01)
        samples = list(range(1000))
        result = ThresholdCalculator.compute(
            samples=samples,
            operator=">=",
            percentile=99.0,
            warning_headroom=0.10,
            critical_headroom=0.20,
        )
        self.assertAlmostEqual(result.percentile_value, 989.01, places=2)
        # warning = 989.01 * 1.10 = 1087.911
        self.assertAlmostEqual(result.new_warning, 1087.911, places=2)
        # critical = 989.01 * 1.20 = 1186.812
        self.assertAlmostEqual(result.new_critical, 1186.812, places=2)
        self.assertEqual(result.sample_count, 1000)

    def test_direction_inversion_for_less_than_operator(self):
        # Low-is-worse: operator is "<", lower-percentile baseline, NEGATIVE headroom
        # Samples 1000..2000: p1 = 1010. With 20% headroom (reducing): critical = 1010 * 0.80 = 808
        samples = list(range(1000, 2001))
        result = ThresholdCalculator.compute(
            samples=samples,
            operator="<",
            percentile=99.0,
            warning_headroom=0.10,
            critical_headroom=0.20,
        )
        self.assertAlmostEqual(result.percentile_value, 1010.0, places=1)
        self.assertAlmostEqual(result.new_warning, 1010.0 * 0.90, places=1)
        self.assertAlmostEqual(result.new_critical, 1010.0 * 0.80, places=1)

    def test_le_operator_same_as_lt(self):
        samples = list(range(100, 200))
        result = ThresholdCalculator.compute(
            samples=samples,
            operator="<=",
            percentile=95.0,
            warning_headroom=0.05,
            critical_headroom=0.10,
        )
        # p5 of 100..199 = 104.95
        self.assertAlmostEqual(result.percentile_value, 104.95, places=1)
        # warning = 104.95 * 0.95; critical = 104.95 * 0.90
        self.assertAlmostEqual(result.new_warning, 104.95 * 0.95, places=1)
        self.assertAlmostEqual(result.new_critical, 104.95 * 0.90, places=1)

    def test_gt_operator_same_as_ge(self):
        samples = [10, 20, 30, 40, 50]
        r1 = ThresholdCalculator.compute(samples, ">", 99.0, 0.10, 0.20)
        r2 = ThresholdCalculator.compute(samples, ">=", 99.0, 0.10, 0.20)
        self.assertEqual(r1.new_warning, r2.new_warning)
        self.assertEqual(r1.new_critical, r2.new_critical)

    def test_single_sample(self):
        result = ThresholdCalculator.compute(
            samples=[42.0],
            operator=">=",
            percentile=99.0,
            warning_headroom=0.10,
            critical_headroom=0.20,
        )
        self.assertEqual(result.percentile_value, 42.0)
        self.assertAlmostEqual(result.new_warning, 46.2, places=1)
        self.assertAlmostEqual(result.new_critical, 50.4, places=1)
        self.assertEqual(result.sample_count, 1)

    def test_all_zeros_produces_zero(self):
        # Caller (orchestrator) is responsible for treating (0, 0) as nonsensical.
        result = ThresholdCalculator.compute(
            samples=[0, 0, 0, 0, 0],
            operator=">=",
            percentile=99.0,
            warning_headroom=0.10,
            critical_headroom=0.20,
        )
        self.assertEqual(result.new_warning, 0.0)
        self.assertEqual(result.new_critical, 0.0)

    def test_zero_headroom(self):
        samples = list(range(1000))
        result = ThresholdCalculator.compute(
            samples=samples,
            operator=">=",
            percentile=99.0,
            warning_headroom=0.0,
            critical_headroom=0.0,
        )
        # p99 of range(1000) = 989.01 under linear-interpolation
        self.assertAlmostEqual(result.new_warning, 989.01, places=2)
        self.assertAlmostEqual(result.new_critical, 989.01, places=2)

    def test_percentile_p50_median(self):
        # Check percentile math for p50 (median)
        samples = [1, 2, 3, 4, 5]
        result = ThresholdCalculator.compute(
            samples=samples,
            operator=">=",
            percentile=50.0,
            warning_headroom=0.0,
            critical_headroom=0.0,
        )
        self.assertEqual(result.percentile_value, 3.0)

    def test_raises_on_empty_samples(self):
        with self.assertRaises(ValueError):
            ThresholdCalculator.compute(
                samples=[],
                operator=">=",
                percentile=99.0,
                warning_headroom=0.10,
                critical_headroom=0.20,
            )

    def test_raises_on_unsupported_operator(self):
        with self.assertRaises(ValueError):
            ThresholdCalculator.compute(
                samples=[1, 2, 3],
                operator="==",
                percentile=99.0,
                warning_headroom=0.10,
                critical_headroom=0.20,
            )

    def test_high_percentile_p99_9(self):
        samples = list(range(10000))
        result = ThresholdCalculator.compute(
            samples=samples,
            operator=">=",
            percentile=99.9,
            warning_headroom=0.0,
            critical_headroom=0.0,
        )
        # p99.9 of 0..9999 = 9989.001 (pos = 9999 * 0.999 = 9989.001)
        self.assertAlmostEqual(result.percentile_value, 9989.001, places=2)


from axonopscli.components.tune_alerts import ExprRewriter


class TestExprRewriter(unittest.TestCase):

    def test_strip_threshold_simple(self):
        bare, op, old = ExprRewriter.strip_threshold("foo_metric >= 50")
        self.assertEqual(bare, "foo_metric")
        self.assertEqual(op, ">=")
        self.assertEqual(old, "50")

    def test_strip_threshold_with_function_call(self):
        bare, op, old = ExprRewriter.strip_threshold(
            "avg(host_CPU{axonfunction='rate',mode='iowait'}) by (host_id) * 100 >= 50"
        )
        self.assertEqual(
            bare,
            "avg(host_CPU{axonfunction='rate',mode='iowait'}) by (host_id) * 100",
        )
        self.assertEqual(op, ">=")
        self.assertEqual(old, "50")

    def test_strip_threshold_with_abs_and_multiplication(self):
        bare, op, old = ExprRewriter.strip_threshold("abs(host_ntp_offset_seconds{}) * 1000 >= 100")
        self.assertEqual(bare, "abs(host_ntp_offset_seconds{}) * 1000")
        self.assertEqual(op, ">=")
        self.assertEqual(old, "100")

    def test_strip_threshold_less_than(self):
        bare, op, old = ExprRewriter.strip_threshold("disk_free_bytes < 1000000")
        self.assertEqual(bare, "disk_free_bytes")
        self.assertEqual(op, "<")
        self.assertEqual(old, "1000000")

    def test_rewrite_replaces_threshold_preserving_operator(self):
        original = "jvm_GarbageCollector_G1_Young_Generation{axonfunction='rate',function='CollectionTime'} >= 1000"
        new_expr = ExprRewriter.rewrite(original, new_warning=825)
        self.assertEqual(
            new_expr,
            "jvm_GarbageCollector_G1_Young_Generation{axonfunction='rate',function='CollectionTime'} >= 825",
        )

    def test_rewrite_preserves_float_format(self):
        new_expr = ExprRewriter.rewrite("foo >= 50", new_warning=44.5)
        self.assertEqual(new_expr, "foo >= 44.5")

    def test_rewrite_emits_integer_when_value_is_whole(self):
        # 1089.0 → "1089" (avoid trailing .0 noise in the JSON)
        new_expr = ExprRewriter.rewrite("foo >= 1000", new_warning=1089.0)
        self.assertEqual(new_expr, "foo >= 1089")

    def test_rewrite_raises_on_unparseable_expr(self):
        with self.assertRaises(ValueError):
            ExprRewriter.rewrite("no_operator_or_value_here", new_warning=42)


from unittest.mock import MagicMock
from types import SimpleNamespace

from axonopscli.components.tune_alerts import MetricQuerier


def _args(org="acme", cluster="prod", v=0):
    return SimpleNamespace(org=org, cluster=cluster, v=v)


class TestMetricQuerier(unittest.TestCase):

    def test_query_builds_correct_url_and_params(self):
        axonops = MagicMock()
        axonops.get_cluster_type.return_value = "cassandra"
        axonops.do_request.return_value = {
            "status": "success",
            "data": {"resultType": "matrix", "result": []},
        }
        q = MetricQuerier(axonops, _args(org="acme", cluster="prod"))

        q.query("foo_metric", start=1_700_000_000, end=1_700_604_800, step="1m")

        self.assertEqual(axonops.do_request.call_count, 1)
        call = axonops.do_request.call_args
        url = call.kwargs.get('url') or call.args[0]
        self.assertIn("/api/v1/query_range/acme/cassandra/prod", url)
        self.assertIn("query=foo_metric", url)
        self.assertIn("start=1700000000", url)
        self.assertIn("end=1700604800", url)
        self.assertIn("step=1m", url)

    def test_query_flattens_prometheus_matrix_response(self):
        axonops = MagicMock()
        axonops.get_cluster_type.return_value = "cassandra"
        axonops.do_request.return_value = {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [
                    {
                        "metric": {"host_id": "h1"},
                        "values": [[1700000000, "10"], [1700000060, "20"], [1700000120, "30"]],
                    },
                    {
                        "metric": {"host_id": "h2"},
                        "values": [[1700000000, "15"], [1700000060, "25"]],
                    },
                ],
            },
        }
        q = MetricQuerier(axonops, _args())

        samples = q.query("foo", start=0, end=1, step="1m")

        self.assertEqual(sorted(samples), [10.0, 15.0, 20.0, 25.0, 30.0])

    def test_query_drops_nulls_and_non_numeric(self):
        axonops = MagicMock()
        axonops.get_cluster_type.return_value = "cassandra"
        axonops.do_request.return_value = {
            "status": "success",
            "data": {
                "resultType": "matrix",
                "result": [{
                    "metric": {},
                    "values": [
                        [1700000000, "10"],
                        [1700000060, "NaN"],
                        [1700000120, None],
                        [1700000180, "30"],
                    ],
                }],
            },
        }
        q = MetricQuerier(axonops, _args())

        samples = q.query("foo", start=0, end=1, step="1m")

        self.assertEqual(samples, [10.0, 30.0])

    def test_query_returns_empty_list_for_empty_result(self):
        axonops = MagicMock()
        axonops.get_cluster_type.return_value = "cassandra"
        axonops.do_request.return_value = {
            "status": "success",
            "data": {"resultType": "matrix", "result": []},
        }
        q = MetricQuerier(axonops, _args())

        samples = q.query("foo", start=0, end=1, step="1m")

        self.assertEqual(samples, [])

    def test_query_propagates_http_errors(self):
        from axonopscli.utils import HTTPCodeError

        axonops = MagicMock()
        axonops.get_cluster_type.return_value = "cassandra"
        axonops.do_request.side_effect = HTTPCodeError("500 Internal Server Error")
        q = MetricQuerier(axonops, _args())

        with self.assertRaises(HTTPCodeError):
            q.query("foo", start=0, end=1, step="1m")

    def test_query_tolerates_malformed_response_shapes(self):
        """Must not crash on any non-conforming shape — return [] instead."""
        malformed_cases = [
            None,
            "not a dict",
            {"data": "oops"},
            {"data": {"result": "oops"}},
            {"data": {"result": ["not-a-dict"]}},
            {"data": {"result": [{"values": "not-a-list"}]}},
            {"data": {"result": [{"values": [42]}]}},  # point is int, not list
            {"data": {"result": [{"values": [[1, "v1", "extra"]]}]}},  # 3-element point
        ]
        for bad in malformed_cases:
            axonops = MagicMock()
            axonops.get_cluster_type.return_value = "cassandra"
            axonops.do_request.return_value = bad
            q = MetricQuerier(axonops, _args())
            # Must not raise; must return [] or a list of successfully-parsed samples
            samples = q.query("foo", start=0, end=1, step="1m")
            self.assertIsInstance(samples, list, f"non-list result for input: {bad!r}")
            # Samples should be empty since none of these shapes contain valid values
            self.assertEqual(samples, [], f"expected [] for malformed input: {bad!r}")


from axonopscli.components.tune_alerts import RuleFilter


class TestRuleFilter(unittest.TestCase):

    def test_no_filters_includes_everything(self):
        f = RuleFilter(include=[], exclude=[], rules=[])
        self.assertTrue(f.accepts("anything"))

    def test_include_glob_matches(self):
        f = RuleFilter(include=["GC*"], exclude=[], rules=[])
        self.assertTrue(f.accepts("GC duration - G1 YoungGen"))
        self.assertFalse(f.accepts("Avg IO wait CPU per Host"))

    def test_exclude_glob_rejects(self):
        f = RuleFilter(include=[], exclude=["NTP*"], rules=[])
        self.assertTrue(f.accepts("GC duration - G1 YoungGen"))
        self.assertFalse(f.accepts("NTP offset (milliseconds)"))

    def test_rule_exact_match(self):
        f = RuleFilter(include=[], exclude=[], rules=["Avg IO wait CPU per Host"])
        self.assertTrue(f.accepts("Avg IO wait CPU per Host"))
        self.assertFalse(f.accepts("GC duration - G1 YoungGen"))

    def test_exclude_overrides_include(self):
        f = RuleFilter(include=["*"], exclude=["GC*"], rules=[])
        self.assertTrue(f.accepts("Avg IO wait CPU per Host"))
        self.assertFalse(f.accepts("GC duration - G1 YoungGen"))

    def test_rules_implies_include_when_other_include_empty(self):
        f = RuleFilter(include=[], exclude=[], rules=["Only This One"])
        self.assertTrue(f.accepts("Only This One"))
        self.assertFalse(f.accepts("Anything Else"))


import json
import os
import tempfile
from unittest.mock import patch

from axonopscli.components.tune_alerts import (
    TuneAlertsOrchestrator,
    TuneAlertsConfig,
    RuleOutcome,
)


def _sample_input(cluster_name="bc1"):
    """Minimal input JSON mimicking the shape of the exported alert_rules.json."""
    return {
        "name": cluster_name,
        "metricrules": [
            {
                "id": "rule-1",
                "alert": "GC duration",
                "expr": "jvm_gc_CollectionTime >= 1000",
                "for": "2m",
                "operator": ">=",
                "criticalValue": 1300,
                "warningValue": 1000,
                "filters": [],
                "annotations": {},
                "integrations": {},
            },
            {
                "id": "rule-2",
                "alert": "NTP offset",
                "expr": "abs(host_ntp_offset_seconds) * 1000 >= 100",
                "for": "5m",
                "operator": ">=",
                "criticalValue": 150,
                "warningValue": 100,
                "filters": [],
                "annotations": {},
                "integrations": {},
            },
        ],
    }


def _default_config(**overrides):
    defaults = dict(
        profile="default",
        percentile=99.0,
        warning_headroom=0.10,
        critical_headroom=0.20,
        min_samples=100,
        # NOTE: raised from 10.0 (plan default) to 100.0 so the NTP rule in
        # _sample_input (baseline warning=100) does not trip the delta clamp
        # when tuned against range(1000) samples (new_warning ≈ 1087.91,
        # ratio ≈ 10.88). test_skips_unreasonable_delta overrides this back
        # to 10.0 to exercise the delta-clamp path explicitly.
        max_delta=100.0,
        include=[],
        exclude=[],
        rules=[],
    )
    defaults.update(overrides)
    return TuneAlertsConfig(**defaults)


class TestTuneAlertsOrchestrator(unittest.TestCase):

    def _make_orch(self, samples_by_metric: dict, config=None):
        from axonopscli.components.tune_alerts import MetricQuerier

        config = config or _default_config()
        axonops = MagicMock()
        axonops.get_cluster_type.return_value = "cassandra"

        orch = TuneAlertsOrchestrator(axonops, _args(org="acme", cluster="bc1"), config)
        # Patch MetricQuerier.query to return canned samples keyed by bare_metric.
        def fake_query(self, promql, start, end, step="1m"):
            return samples_by_metric.get(promql, [])

        orch._querier_cls = MetricQuerier  # allow override for test patching
        orch._fake_query = fake_query
        return orch

    def test_tunes_happy_path_with_sufficient_samples(self):
        samples = list(range(1000))  # p99 = 990
        orch = self._make_orch({
            "jvm_gc_CollectionTime": samples,
            "abs(host_ntp_offset_seconds) * 1000": samples,
        })
        with patch.object(MetricQuerier, 'query', new=orch._fake_query):
            result = orch.tune_all(_sample_input())

        self.assertEqual(len(result.outcomes), 2)
        for outcome in result.outcomes:
            self.assertEqual(outcome.status, "tuned")
            # p99 of range(1000) = 989.01 (linear interp), critical headroom 0.20 => 1186.812
            self.assertAlmostEqual(outcome.new_critical, 1186.81, places=2)

    def test_skips_insufficient_samples(self):
        orch = self._make_orch({
            "jvm_gc_CollectionTime": [1, 2, 3],  # only 3 samples, below 100 min
            "abs(host_ntp_offset_seconds) * 1000": list(range(1000)),
        })
        with patch.object(MetricQuerier, 'query', new=orch._fake_query):
            result = orch.tune_all(_sample_input())

        outcomes_by_name = {o.rule_name: o for o in result.outcomes}
        self.assertEqual(outcomes_by_name["GC duration"].status, "skipped")
        self.assertIn("insufficient data", outcomes_by_name["GC duration"].reason)
        self.assertEqual(outcomes_by_name["NTP offset"].status, "tuned")

    def test_skips_nonsensical_zero_threshold(self):
        # All zeros → new_critical = 0 → hard floor skip
        orch = self._make_orch({
            "jvm_gc_CollectionTime": [0] * 1000,
            "abs(host_ntp_offset_seconds) * 1000": list(range(1000)),
        })
        with patch.object(MetricQuerier, 'query', new=orch._fake_query):
            result = orch.tune_all(_sample_input())

        o = {o.rule_name: o for o in result.outcomes}
        self.assertEqual(o["GC duration"].status, "skipped")
        self.assertIn("nonsensical", o["GC duration"].reason)

    def test_skips_unreasonable_delta(self):
        # Original critical=1300, p99 samples produce new_critical of ~12
        # ratio 1300/12 = 108, exceeds max_delta 10 → skip
        # Override max_delta back to 10.0 (the _default_config uses 100.0 to let
        # happy-path NTP tuning succeed; see _default_config note).
        config = _default_config(min_samples=5, max_delta=10.0)
        orch = self._make_orch(
            {"jvm_gc_CollectionTime": list(range(10)), "abs(host_ntp_offset_seconds) * 1000": list(range(10))},
            config=config,
        )
        with patch.object(MetricQuerier, 'query', new=orch._fake_query):
            result = orch.tune_all(_sample_input())
        o = {o.rule_name: o for o in result.outcomes}
        self.assertEqual(o["GC duration"].status, "skipped")
        self.assertIn("unreasonable delta", o["GC duration"].reason)

    def test_filter_excludes_rule(self):
        config = _default_config(exclude=["NTP*"])
        orch = self._make_orch({"jvm_gc_CollectionTime": list(range(1000))}, config=config)
        with patch.object(MetricQuerier, 'query', new=orch._fake_query):
            result = orch.tune_all(_sample_input())

        o = {o.rule_name: o for o in result.outcomes}
        self.assertEqual(o["NTP offset"].status, "filtered")
        self.assertEqual(o["GC duration"].status, "tuned")

    def test_tuned_json_updates_threshold_and_expr(self):
        orch = self._make_orch({
            "jvm_gc_CollectionTime": list(range(1000)),
            "abs(host_ntp_offset_seconds) * 1000": list(range(1000)),
        })
        with patch.object(MetricQuerier, 'query', new=orch._fake_query):
            result = orch.tune_all(_sample_input())

        tuned = result.tuned_json
        rule = tuned["metricrules"][0]
        # p99 of range(1000) = 989.01 (linear interp)
        # new_warning  = 989.01 * 1.10 = 1087.911 → _round_threshold → 1087.91
        # new_critical = 989.01 * 1.20 = 1186.812 → _round_threshold → 1186.81
        self.assertAlmostEqual(rule["warningValue"], 1087.91, places=2)
        self.assertAlmostEqual(rule["criticalValue"], 1186.81, places=2)
        # expr must carry the new warning threshold (not the critical)
        self.assertTrue(
            rule["expr"].endswith(" >= 1087.91"),
            f"unexpected expr suffix: {rule['expr']!r}",
        )

    def test_query_failure_marks_rule_skipped(self):
        from axonopscli.utils import HTTPCodeError

        def failing_query(self, promql, start, end, step="1m"):
            if "jvm_gc" in promql:
                raise HTTPCodeError("500 server error")
            return list(range(1000))

        config = _default_config()
        axonops = MagicMock()
        axonops.get_cluster_type.return_value = "cassandra"
        orch = TuneAlertsOrchestrator(axonops, _args(org="acme", cluster="bc1"), config)

        with patch.object(MetricQuerier, 'query', new=failing_query):
            result = orch.tune_all(_sample_input())

        o = {o.rule_name: o for o in result.outcomes}
        self.assertEqual(o["GC duration"].status, "skipped")
        self.assertIn("query failed", o["GC duration"].reason)
        # Other rule still tuned
        self.assertEqual(o["NTP offset"].status, "tuned")


import stat


class TestTuneAlertsOrchestratorOutput(unittest.TestCase):

    def _run_once(self, tmp_path, samples_all=None):
        if samples_all is None:
            samples_all = list(range(1000))
        config = _default_config()
        axonops = MagicMock()
        axonops.get_cluster_type.return_value = "cassandra"
        orch = TuneAlertsOrchestrator(axonops, _args(org="acme", cluster="bc1"), config)

        input_path = os.path.join(tmp_path, "alert_rules.json")
        with open(input_path, "w") as f:
            json.dump(_sample_input(cluster_name="bc1"), f)

        def fake_query(self, promql, start, end, step="1m"):
            return samples_all

        with patch.object(MetricQuerier, 'query', new=fake_query):
            data = orch.load_input(input_path)
            result = orch.tune_all(data)
            json_path = orch.write_output(input_path, result)
            report_path = orch.write_audit_report(input_path, result)
        return orch, result, input_path, json_path, report_path

    def test_output_filename_uses_cluster_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, input_path, json_path, report_path = self._run_once(tmp)
            self.assertEqual(
                os.path.basename(json_path),
                "alert_rules.tuned.for.bc1.json",
            )
            self.assertEqual(
                os.path.basename(report_path),
                "alert_rules.tuned.for.bc1.report.md",
            )

    def test_output_file_mode_is_0600(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, json_path, _ = self._run_once(tmp)
            mode = stat.S_IMODE(os.stat(json_path).st_mode)
            self.assertEqual(mode, 0o600)

    def test_audit_report_file_mode_is_0644(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, _, report_path = self._run_once(tmp)
            mode = stat.S_IMODE(os.stat(report_path).st_mode)
            self.assertEqual(mode, 0o644)

    def test_audit_report_contains_tuned_and_skipped_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, _, report_path = self._run_once(tmp)
            content = open(report_path).read()
            self.assertIn("# Alert tuning report", content)
            self.assertIn("Profile:", content)
            self.assertIn("Window:", content)
            self.assertIn("## Summary", content)
            self.assertIn("## Tuned rules", content)
            # Must list each tuned rule name
            self.assertIn("GC duration", content)
            self.assertIn("NTP offset", content)

    def test_print_summary_outputs_counts(self):
        import io, contextlib
        with tempfile.TemporaryDirectory() as tmp:
            orch, result, _, json_path, _ = self._run_once(tmp)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                orch.print_summary(result, json_path)
            out = buf.getvalue()
            self.assertIn("Tuned 2", out)
            self.assertIn("alert_rules.tuned.for.bc1.json", out)

    def test_tuned_json_has_correct_cluster_name_and_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, json_path, _ = self._run_once(tmp)
            with open(json_path) as f:
                data = json.load(f)
            self.assertEqual(data["name"], "bc1")
            self.assertEqual(len(data["metricrules"]), 2)
            # Must have preserved all fields, only changed warning/critical/expr
            rule = data["metricrules"][0]
            self.assertIn("id", rule)
            self.assertIn("filters", rule)
            self.assertIn("annotations", rule)


if __name__ == "__main__":
    unittest.main()
