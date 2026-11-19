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


from axonopscli.components.tune_alerts import parse_set_label_arg


class TestExprRewriterSetLabel(unittest.TestCase):

    def test_rewrites_regex_comma_list_to_single_exact_value(self):
        # The broken comma-list `=~` selector → single exact-match value.
        expr = ("cas_Keyspace_ReadLatency{function='95thPercentile',"
                "keyspace=~'system,system_auth,myks'}")
        out = ExprRewriter.set_label(expr, "keyspace", "myks")
        self.assertEqual(
            out,
            "cas_Keyspace_ReadLatency{function='95thPercentile',keyspace='myks'}",
        )

    def test_rewrites_exact_comma_list_to_single_value(self):
        # `=` exact-match comma blob is also collapsed to one value.
        expr = "cas_Table_AllMemtablesHeapSize{rack='',keyspace='system,myks'}"
        out = ExprRewriter.set_label(expr, "keyspace", "myks")
        self.assertEqual(
            out, "cas_Table_AllMemtablesHeapSize{rack='',keyspace='myks'}"
        )

    def test_metric_glob_confines_overloaded_label(self):
        # scope means a table on cas_Table_*, but a request type elsewhere.
        # Only the cas_Table_* selector should be rewritten.
        expr = ("sum(cas_Table_CoordinatorWriteLatency{scope=~'events,mytable'}) "
                "+ cas_ClientRequest_Latency{scope='Read.*'}")
        out = ExprRewriter.set_label(expr, "scope", "mytable", metric_glob="cas_Table_*")
        self.assertEqual(
            out,
            "sum(cas_Table_CoordinatorWriteLatency{scope='mytable'}) "
            "+ cas_ClientRequest_Latency{scope='Read.*'}",
        )

    def test_absent_label_is_left_untouched(self):
        # No keyspace label present → expr unchanged (never injects).
        expr = "host_CPU{axonfunction='rate',mode='iowait'}"
        self.assertEqual(ExprRewriter.set_label(expr, "keyspace", "myks"), expr)

    def test_does_not_touch_by_grouping_clause(self):
        # `by (keyspace, table)` grouping must not be rewritten — only the
        # selector body inside the braces.
        expr = ("sum by (remoteIP, keyspace, table) "
                "(client_throughput_write{keyspace=~'a,myks',table=~'x,mytable'})")
        out = ExprRewriter.set_label(expr, "keyspace", "myks")
        out = ExprRewriter.set_label(out, "table", "mytable")
        self.assertEqual(
            out,
            "sum by (remoteIP, keyspace, table) "
            "(client_throughput_write{keyspace='myks',table='mytable'})",
        )

    def test_rewrites_inside_delta_window_selector(self):
        expr = "delta(cas_ThreadPools_internal{scope=~'MutationStage',dc=~'BC1'}[1m])"
        out = ExprRewriter.set_label(expr, "dc", "BC2")
        self.assertEqual(
            out, "delta(cas_ThreadPools_internal{scope=~'MutationStage',dc='BC2'}[1m])"
        )


class TestParseSetLabelArg(unittest.TestCase):

    def test_plain_label_value(self):
        self.assertEqual(parse_set_label_arg("keyspace=myks"),
                         (None, "keyspace", "myks"))

    def test_metric_glob_prefix(self):
        self.assertEqual(parse_set_label_arg("cas_Table_*:scope=mytable"),
                         ("cas_Table_*", "scope", "mytable"))

    def test_strips_whitespace(self):
        self.assertEqual(parse_set_label_arg(" table = mytable "),
                         (None, "table", "mytable"))

    def test_missing_equals_raises(self):
        with self.assertRaises(ValueError):
            parse_set_label_arg("keyspace")

    def test_invalid_label_name_raises(self):
        with self.assertRaises(ValueError):
            parse_set_label_arg("key-space=myks")

    def test_value_with_quote_raises(self):
        with self.assertRaises(ValueError):
            parse_set_label_arg("keyspace=sub'ks")

    def test_empty_value_raises(self):
        with self.assertRaises(ValueError):
            parse_set_label_arg("keyspace=")


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
        # query_range is served at the base URL without org/cluster path
        # segments; cluster context is carried by promql label filters.
        self.assertTrue(url.startswith("/api/v1/query_range?"),
                        f"unexpected URL: {url!r}")
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


def _sample_input(cluster_name="demo"):
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

        orch = TuneAlertsOrchestrator(axonops, _args(org="acme", cluster="demo"), config)
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
        orch = TuneAlertsOrchestrator(axonops, _args(org="acme", cluster="demo"), config)

        with patch.object(MetricQuerier, 'query', new=failing_query):
            result = orch.tune_all(_sample_input())

        o = {o.rule_name: o for o in result.outcomes}
        self.assertEqual(o["GC duration"].status, "skipped")
        self.assertIn("query failed", o["GC duration"].reason)
        # Other rule still tuned
        self.assertEqual(o["NTP offset"].status, "tuned")

    def test_unreasonable_delta_treats_malformed_old_as_skip_reason(self):
        """Old thresholds that aren't coercible to float should surface a
        clear 'cannot evaluate delta' skip reason, not silently tune."""
        # Construct an input with a malformed old threshold
        input_json = {
            "name": "demo",
            "metricrules": [
                {
                    "id": "rule-x",
                    "alert": "Malformed Threshold Rule",
                    "expr": "foo_metric >= 100",
                    "for": "5m",
                    "operator": ">=",
                    "criticalValue": "N/A",  # malformed
                    "warningValue": 100,
                    "filters": [],
                    "annotations": {},
                    "integrations": {},
                },
            ],
        }
        orch = self._make_orch({"foo_metric": list(range(1000))})
        with patch.object(MetricQuerier, 'query', new=orch._fake_query):
            result = orch.tune_all(input_json)

        outcome = result.outcomes[0]
        self.assertEqual(outcome.status, "skipped")
        self.assertIn("cannot evaluate delta", outcome.reason)

    def test_percent_metric_clamps_at_100_via_star_100(self):
        """Expressions ending in '* 100' with 0-100 bounded old thresholds
        are treated as percentages; tuned values cannot exceed 100."""
        input_json = {
            "name": "demo",
            "metricrules": [
                {
                    "id": "rule-disk",
                    "alert": "Disk % Usage",
                    "expr": "avg(disk_used / disk_total) * 100 >= 75",
                    "for": "5m",
                    "operator": ">=",
                    "criticalValue": 80,
                    "warningValue": 75,
                    "filters": [], "annotations": {}, "integrations": {},
                },
            ],
        }
        high_samples = [85] * 1000
        orch = self._make_orch({"avg(disk_used / disk_total) * 100": high_samples})
        with patch.object(MetricQuerier, 'query', new=orch._fake_query):
            result = orch.tune_all(input_json)

        outcome = result.outcomes[0]
        self.assertEqual(outcome.status, "tuned")
        self.assertLessEqual(outcome.new_warning, 100.0)
        self.assertLessEqual(outcome.new_critical, 100.0)

    def test_percent_metric_clamps_at_100_via_metric_name(self):
        """A metric name containing 'Percent' is treated as a 0-100 value
        when both old thresholds are in 0-100. Catches expressions like
        `host_Disk_UsedPercent{...} >= 75` which carry no `* 100` suffix."""
        input_json = {
            "name": "demo",
            "metricrules": [
                {
                    "id": "rule-disk",
                    "alert": "Disk % Usage Workarea",
                    "expr": "host_Disk_UsedPercent{mountpoint=~'/workarea'} >= 75",
                    "for": "5m",
                    "operator": ">=",
                    "criticalValue": 80,
                    "warningValue": 75,
                    "filters": [], "annotations": {}, "integrations": {},
                },
            ],
        }
        high_samples = [85] * 1000
        orch = self._make_orch({
            "host_Disk_UsedPercent{mountpoint=~'/workarea'}": high_samples,
        })
        with patch.object(MetricQuerier, 'query', new=orch._fake_query):
            result = orch.tune_all(input_json)

        outcome = result.outcomes[0]
        self.assertEqual(outcome.status, "tuned")
        self.assertLessEqual(outcome.new_warning, 100.0)
        self.assertLessEqual(outcome.new_critical, 100.0)

    def test_percent_clamp_skipped_when_old_threshold_exceeds_100(self):
        """If old threshold is already > 100, the `* 100` is a unit
        conversion (e.g. ms→us), not a percentage — do not clamp."""
        input_json = {
            "name": "demo",
            "metricrules": [
                {
                    "id": "rule-latency",
                    "alert": "Some latency",
                    "expr": "rate(foo) * 100 >= 500",  # ms→us conversion idiom
                    "for": "5m",
                    "operator": ">=",
                    "criticalValue": 750,
                    "warningValue": 500,
                    "filters": [], "annotations": {}, "integrations": {},
                },
            ],
        }
        # p99 of range(1000) = 989.01 → new_warning ≈ 1087.91
        # Not clamped (old=500 > 100 triggers the guard).
        orch = self._make_orch({"rate(foo) * 100": list(range(1000))})
        with patch.object(MetricQuerier, 'query', new=orch._fake_query):
            result = orch.tune_all(input_json)

        outcome = result.outcomes[0]
        self.assertEqual(outcome.status, "tuned")
        # If the percent clamp had incorrectly fired, new_warning would have
        # been 100. It should remain the unclamped p99 × headroom value.
        self.assertGreater(outcome.new_warning, 100.0)
        self.assertGreater(outcome.new_critical, 100.0)


import stat


class TestTuneAlertsOrchestratorOutput(unittest.TestCase):

    def _run_once(self, tmp_path, samples_all=None):
        if samples_all is None:
            samples_all = list(range(1000))
        config = _default_config()
        axonops = MagicMock()
        axonops.get_cluster_type.return_value = "cassandra"
        orch = TuneAlertsOrchestrator(axonops, _args(org="acme", cluster="demo"), config)

        input_path = os.path.join(tmp_path, "alert_rules.json")
        with open(input_path, "w") as f:
            json.dump(_sample_input(cluster_name="demo"), f)

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
                "alert_rules.tuned.for.demo.json",
            )
            self.assertEqual(
                os.path.basename(report_path),
                "alert_rules.tuned.for.demo.report.md",
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
            self.assertIn("alert_rules.tuned.for.demo.json", out)

    def test_tuned_json_has_correct_cluster_name_and_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, _, _, json_path, _ = self._run_once(tmp)
            with open(json_path) as f:
                data = json.load(f)
            self.assertEqual(data["name"], "demo")
            self.assertEqual(len(data["metricrules"]), 2)
            # Must have preserved all fields, only changed warning/critical/expr
            rule = data["metricrules"][0]
            self.assertIn("id", rule)
            self.assertIn("filters", rule)
            self.assertIn("annotations", rule)


class TestApplicationRunTuneAlerts(unittest.TestCase):

    def test_application_run_tune_alerts_end_to_end(self):
        from axonopscli.application import Application
        from axonopscli.axonops import AxonOps

        with tempfile.TemporaryDirectory() as tmp:
            # Write an input alert_rules.json
            input_path = os.path.join(tmp, "alert_rules.json")
            with open(input_path, "w") as f:
                json.dump(_sample_input(cluster_name="demo"), f)

            # Canned query_range response yielding p99 ≈ 990
            samples = list(range(1000))
            prom_response = {
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [{
                        "metric": {},
                        "values": [[i, str(float(v))] for i, v in enumerate(samples)],
                    }],
                },
            }
            with patch.object(AxonOps, 'do_request', return_value=prom_response):
                Application().run([
                    "--org", "acme", "--cluster", "demo", "--token", "t",
                    "tune-alerts", "--input", input_path,
                ])

            # Verify output files exist
            self.assertTrue(os.path.exists(os.path.join(tmp, "alert_rules.tuned.for.demo.json")))
            self.assertTrue(os.path.exists(os.path.join(tmp, "alert_rules.tuned.for.demo.report.md")))

    def test_application_run_tune_alerts_profile_quiet(self):
        from axonopscli.application import Application
        from axonopscli.axonops import AxonOps

        with tempfile.TemporaryDirectory() as tmp:
            input_path = os.path.join(tmp, "alert_rules.json")
            with open(input_path, "w") as f:
                json.dump(_sample_input(cluster_name="demo"), f)

            samples = list(range(1000))
            prom_response = {
                "status": "success",
                "data": {
                    "resultType": "matrix",
                    "result": [{
                        "metric": {},
                        "values": [[i, str(float(v))] for i, v in enumerate(samples)],
                    }],
                },
            }
            with patch.object(AxonOps, 'do_request', return_value=prom_response):
                Application().run([
                    "--org", "acme", "--cluster", "demo", "--token", "t",
                    "tune-alerts", "--input", input_path, "--profile", "quiet",
                ])

            out_path = os.path.join(tmp, "alert_rules.tuned.for.demo.json")
            with open(out_path) as f:
                out = json.load(f)
            # Quiet profile: p99.9 + 50% critical headroom on 1000 samples → p99.9 ≈ 999, critical ≈ 1498.5
            self.assertGreater(out["metricrules"][0]["criticalValue"], 1400)


class TestTuneAlertsFromApi(unittest.TestCase):

    def test_from_api_fetches_rules_endpoint_and_writes_output(self):
        from axonopscli.application import Application
        from axonopscli.axonops import AxonOps

        with tempfile.TemporaryDirectory() as tmp:
            # Canned: /api/v1/alert-rules returns _sample_input; /query_range returns samples
            alert_rules_body = _sample_input(cluster_name="demo")
            prom = {
                "status": "success",
                "data": {"resultType": "matrix", "result": [{"metric": {}, "values": [[i, str(float(v))] for i, v in enumerate(range(1000))]}]},
            }

            def fake_do_request(self, url, method='GET', **kwargs):
                if "alert-rules" in url:
                    return alert_rules_body
                if "query_range" in url:
                    return prom
                return {}

            with patch.object(AxonOps, 'do_request', new=fake_do_request):
                Application().run([
                    "--org", "acme", "--cluster", "demo", "--token", "t",
                    "tune-alerts", "--from-api", "--output-dir", tmp,
                ])

            self.assertTrue(os.path.exists(os.path.join(tmp, "alert_rules.tuned.for.demo.json")))

    def test_from_api_and_input_are_mutually_exclusive(self):
        from axonopscli.application import Application

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                Application().run([
                    "--org", "acme", "--cluster", "demo", "--token", "t",
                    "tune-alerts",
                    "--from-api", "--output-dir", tmp,
                    "--input", "/some/path.json",
                ])

    def test_neither_input_nor_from_api_errors(self):
        from axonopscli.application import Application

        with self.assertRaises(SystemExit):
            Application().run([
                "--org", "acme", "--cluster", "demo", "--token", "t",
                "tune-alerts",
            ])


from datetime import datetime, timezone


def _day_range(date_str):
    """Return (start_ts, end_ts) for the given YYYY-MM-DD UTC day."""
    day = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    start = int(day.timestamp())
    end = start + 24 * 60 * 60 - 1
    return (start, end)


class TestIncidentFlag(unittest.TestCase):

    def _run_with_incident(self, tmp, input_json, baseline_samples, incident_samples,
                           incident_date="2026-04-10", extra_args=None):
        """Helper: patches MetricQuerier so baseline query (excluding incident)
        returns baseline_samples and incident-window query returns incident_samples.
        The orchestrator differentiates calls by the start timestamp."""
        from axonopscli.application import Application

        input_path = os.path.join(tmp, "alert_rules.json")
        with open(input_path, "w") as f:
            json.dump(input_json, f)

        incident_start, incident_end = _day_range(incident_date)

        def fake_query(self, promql, start, end, step="1m"):
            # If the window is exactly the incident day, return incident samples
            if start == incident_start and end == incident_end:
                return incident_samples
            # Otherwise baseline (7d, excluding incident) — return baseline
            return baseline_samples

        argv = [
            "--org", "acme", "--cluster", "demo", "--token", "t",
            "tune-alerts", "--input", input_path,
            "--incident", incident_date,
        ]
        if extra_args:
            argv.extend(extra_args)

        with patch('axonopscli.components.tune_alerts.MetricQuerier.query', new=fake_query):
            Application().run(argv)

        with open(os.path.join(tmp, "alert_rules.tuned.for.demo.json")) as f:
            tuned = json.load(f)
        with open(os.path.join(tmp, "alert_rules.tuned.for.demo.report.md")) as f:
            report = f.read()
        return tuned, report

    def test_incident_day_verified_no_adjustment_needed(self):
        # Baseline range(100) → p99 ≈ 98.01; critical = 98.01 * 1.20 ≈ 117.612
        # Incident peak = 700 → 700 >= 117.612 → "Yes (baseline)", no adjustment.
        # --max-delta 100 prevents the GC rule (old_critical=1300) from being
        # skipped by the delta clamp (ratio 1300/117.612 ≈ 11.05).
        with tempfile.TemporaryDirectory() as tmp:
            tuned, report = self._run_with_incident(
                tmp,
                _sample_input(cluster_name="demo"),
                baseline_samples=list(range(100)),   # p99 ≈ 98.01
                incident_samples=[500, 600, 700],    # peak 700, way above 117.612
                extra_args=["--max-delta", "100"],
            )
            self.assertIn("Incident coverage (2026-04-10)", report)
            self.assertIn("Yes (baseline)", report)
            # No adjustment → critical stays at baseline-derived value
            rule = tuned["metricrules"][0]
            self.assertLess(rule["criticalValue"], 200)

    def test_incident_adjusts_threshold_when_baseline_would_miss(self):
        # Baseline range(1000) → p99 ≈ 989.01; critical = 989.01 * 1.20 ≈ 1186.812
        # Incident peak = 800 → 800 < 1186.812 (would miss) AND 800 < 989.01
        # (peak within baseline normal) → metric NOT impacted → no adjustment.
        with tempfile.TemporaryDirectory() as tmp:
            tuned, report = self._run_with_incident(
                tmp,
                _sample_input(cluster_name="demo"),
                baseline_samples=list(range(1000)),  # p99 ≈ 989.01
                incident_samples=[500, 700, 800],    # peak 800 < 989.01 (baseline p99)
            )
            self.assertIn("metric not impacted by incident", report)

    def test_incident_metric_impacted_triggers_adjustment(self):
        # Baseline range(1, 101) → p99 ≈ 99.01; critical = 99.01 * 1.20 ≈ 118.812
        # Incident peak = 100 → 100 > 99.01 (impacted), but 100 < 118.812
        # (would miss) → adjust critical to min(118.812, 100*0.95) = 95.
        # --max-delta 100 prevents delta-clamp skip (1300/95 ≈ 13.68).
        with tempfile.TemporaryDirectory() as tmp:
            tuned, report = self._run_with_incident(
                tmp,
                _sample_input(cluster_name="demo"),
                baseline_samples=list(range(1, 101)),   # p99 ≈ 99.01
                incident_samples=[50, 80, 100],          # peak 100 > 99.01 (impacted), but < 118.812 (would miss)
                extra_args=["--max-delta", "100"],
            )
            self.assertIn("Yes (adjusted)", report)
            rule = tuned["metricrules"][0]
            # Adjusted critical = 100 * 0.95 = 95
            self.assertLessEqual(rule["criticalValue"], 100)

    def test_multiple_incidents(self):
        # Both incident dates should appear in report.
        from axonopscli.application import Application

        with tempfile.TemporaryDirectory() as tmp:
            input_path = os.path.join(tmp, "alert_rules.json")
            with open(input_path, "w") as f:
                json.dump(_sample_input(cluster_name="demo"), f)

            def fake_query(self, promql, start, end, step="1m"):
                return list(range(1000))

            with patch('axonopscli.components.tune_alerts.MetricQuerier.query', new=fake_query):
                Application().run([
                    "--org", "acme", "--cluster", "demo", "--token", "t",
                    "tune-alerts", "--input", input_path,
                    "--incident", "2026-04-10", "--incident", "2026-04-11",
                ])

            with open(os.path.join(tmp, "alert_rules.tuned.for.demo.report.md")) as f:
                report = f.read()
            self.assertIn("Incident coverage (2026-04-10)", report)
            self.assertIn("Incident coverage (2026-04-11)", report)

    def test_multiple_incidents_chain_adjustments_reported_correctly(self):
        """When two incidents both trigger adjustment, the second incident's
        'action' should reference the value AFTER the first adjustment,
        not the original baseline-derived value."""
        from axonopscli.application import Application
        from axonopscli.axonops import AxonOps

        with tempfile.TemporaryDirectory() as tmp:
            input_path = os.path.join(tmp, "alert_rules.json")
            with open(input_path, "w") as f:
                json.dump(_sample_input(cluster_name="demo"), f)

            incident_1_start, _ = _day_range("2026-04-10")
            incident_2_start, _ = _day_range("2026-04-11")

            def fake_query(self, promql, start, end, step="1m"):
                if start == incident_1_start:
                    return [80, 95, 105]   # peak 105 > p99=99.01 → impacted, but 105 < critical_baseline=118.81 → adjust
                if start == incident_2_start:
                    return [80, 95, 99.5]  # peak 99.5 > p99=99.01 → impacted, but 99.5 < post-incident-1 critical (~99.75) → adjust
                return list(range(1, 101))  # baseline → p99 ≈ 99.01

            with patch('axonopscli.components.tune_alerts.MetricQuerier.query', new=fake_query):
                Application().run([
                    "--org", "acme", "--cluster", "demo", "--token", "t",
                    "tune-alerts", "--input", input_path,
                    "--incident", "2026-04-10", "--incident", "2026-04-11",
                    "--max-delta", "100",
                ])

            with open(os.path.join(tmp, "alert_rules.tuned.for.demo.report.md")) as f:
                report = f.read()

            inc2_idx = report.find("Incident coverage (2026-04-11)")
            self.assertGreater(inc2_idx, 0, "Incident 2 section missing")
            inc2_section = report[inc2_idx:inc2_idx + 2000]

            # With the bug: "critical 118.81 → ..." (original baseline)
            # With the fix: "critical 99.75 → ..." (post-incident-1 value)
            self.assertNotIn("118.81", inc2_section,
                             f"Incident 2 row references original baseline:\n{inc2_section}")
            self.assertIn("99.75", inc2_section,
                          f"Expected incident 2 'from' to be post-incident-1 value:\n{inc2_section}")


class TestPolicyPinning(unittest.TestCase):
    """Policy-pinned thresholds override workload-derived tuning for
    matching rule-name globs."""

    def _make_orch_with_policy(self, pinned_rules):
        config = _default_config()
        config.pinned_rules = pinned_rules
        axonops = MagicMock()
        axonops.get_cluster_type.return_value = "cassandra"
        orch = TuneAlertsOrchestrator(axonops, _args(org="acme", cluster="demo"), config)
        return orch

    def test_pinned_rule_gets_fixed_values_without_querying_api(self):
        # Canned query that would raise — if MetricQuerier is touched, test fails.
        def exploding_query(self, promql, start, end, step="1m"):
            raise AssertionError("MetricQuerier.query must not be called for a pinned rule")

        input_json = {
            "name": "demo",
            "metricrules": [
                {
                    "id": "rule-disk",
                    "alert": "Disk % Usage Workarea",
                    "expr": "host_Disk_UsedPercent{mountpoint=~'/workarea'} >= 75",
                    "for": "5m", "operator": ">=",
                    "warningValue": 75, "criticalValue": 80,
                    "filters": [], "annotations": {}, "integrations": {},
                },
            ],
        }
        orch = self._make_orch_with_policy([
            {"pattern": "Disk *", "warning": 70, "critical": 80},
        ])
        with patch.object(MetricQuerier, 'query', new=exploding_query):
            result = orch.tune_all(input_json)

        outcome = result.outcomes[0]
        self.assertEqual(outcome.status, "pinned")
        self.assertEqual(outcome.new_warning, 70)
        self.assertEqual(outcome.new_critical, 80)
        self.assertEqual(outcome.pinned_pattern, "Disk *")

    def test_pinned_rule_updates_expr_with_new_warning(self):
        input_json = {
            "name": "demo",
            "metricrules": [
                {
                    "id": "rule-disk",
                    "alert": "Disk % Usage Workarea",
                    "expr": "host_Disk_UsedPercent{} >= 75",
                    "for": "5m", "operator": ">=",
                    "warningValue": 75, "criticalValue": 80,
                    "filters": [], "annotations": {}, "integrations": {},
                },
            ],
        }
        orch = self._make_orch_with_policy([
            {"pattern": "Disk *", "warning": 70, "critical": 80},
        ])
        result = orch.tune_all(input_json)

        self.assertEqual(result.tuned_json["metricrules"][0]["expr"],
                         "host_Disk_UsedPercent{} >= 70")
        self.assertEqual(result.tuned_json["metricrules"][0]["warningValue"], 70)
        self.assertEqual(result.tuned_json["metricrules"][0]["criticalValue"], 80)

    def test_non_matching_rule_follows_normal_tuning_pipeline(self):
        input_json = _sample_input(cluster_name="demo")
        orch = self._make_orch_with_policy([
            {"pattern": "Disk *", "warning": 70, "critical": 80},
        ])

        def canned_query(self, promql, start, end, step="1m"):
            return list(range(1000))

        with patch.object(MetricQuerier, 'query', new=canned_query):
            result = orch.tune_all(input_json)

        # Neither sample rule is named "Disk *"; both go through normal tuning.
        for outcome in result.outcomes:
            self.assertNotEqual(outcome.status, "pinned",
                                f"{outcome.rule_name} should not be pinned")

    def test_filtered_rule_is_not_pinned(self):
        """Filter wins over pin: a rule excluded by --exclude is not considered
        for pinning (no work is done on it at all)."""
        input_json = {
            "name": "demo",
            "metricrules": [
                {
                    "id": "rule-disk",
                    "alert": "Disk % Usage Workarea",
                    "expr": "host_Disk_UsedPercent{} >= 75",
                    "for": "5m", "operator": ">=",
                    "warningValue": 75, "criticalValue": 80,
                    "filters": [], "annotations": {}, "integrations": {},
                },
            ],
        }
        config = _default_config(exclude=["Disk *"])
        config.pinned_rules = [
            {"pattern": "Disk *", "warning": 70, "critical": 80},
        ]
        axonops = MagicMock()
        axonops.get_cluster_type.return_value = "cassandra"
        orch = TuneAlertsOrchestrator(axonops, _args(), config)
        result = orch.tune_all(input_json)

        self.assertEqual(result.outcomes[0].status, "filtered")

    def test_pinned_rule_with_unparseable_expr_skips(self):
        """A pinned rule whose expr can't be parsed is surfaced as skipped
        with a clear reason — we can't update the expr without knowing the
        operator."""
        input_json = {
            "name": "demo",
            "metricrules": [
                {
                    "id": "rule-bad",
                    "alert": "Bad Disk Rule",
                    "expr": "malformed_no_operator",
                    "for": "5m", "operator": ">=",
                    "warningValue": 75, "criticalValue": 80,
                    "filters": [], "annotations": {}, "integrations": {},
                },
            ],
        }
        orch = self._make_orch_with_policy([
            {"pattern": "Bad *", "warning": 70, "critical": 80},
        ])
        result = orch.tune_all(input_json)

        self.assertEqual(result.outcomes[0].status, "skipped")
        self.assertIn("cannot parse expr for pinning", result.outcomes[0].reason)

    def test_audit_report_includes_pinned_section(self):
        import tempfile

        input_json = {
            "name": "demo",
            "metricrules": [
                {
                    "id": "rule-disk",
                    "alert": "Disk % Usage Workarea",
                    "expr": "host_Disk_UsedPercent{} >= 75",
                    "for": "5m", "operator": ">=",
                    "warningValue": 75, "criticalValue": 80,
                    "filters": [], "annotations": {}, "integrations": {},
                },
            ],
        }
        orch = self._make_orch_with_policy([
            {"pattern": "Disk *", "warning": 70, "critical": 80},
        ])
        result = orch.tune_all(input_json)

        with tempfile.TemporaryDirectory() as tmp:
            input_path = os.path.join(tmp, "alert_rules.json")
            with open(input_path, "w") as f:
                json.dump(input_json, f)
            report_path = orch.write_audit_report(input_path, result)
            report = open(report_path).read()

        self.assertIn("## Pinned rules (policy override)", report)
        self.assertIn("Disk % Usage Workarea", report)
        self.assertIn("Disk *", report)


class TestPolicyFileLoader(unittest.TestCase):
    """The --policy flag loads and validates a JSON policy file."""

    def _write_policy(self, tmp, content):
        import tempfile
        path = os.path.join(tmp, "policy.json")
        with open(path, "w") as f:
            if isinstance(content, str):
                f.write(content)
            else:
                json.dump(content, f)
        return path

    def test_loads_valid_policy(self):
        import tempfile
        from axonopscli.application import Application

        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_policy(tmp, {
                "pinned_thresholds": [
                    {"pattern": "Disk *", "warning": 70, "critical": 80},
                ],
            })
            pinned = Application._load_policy_file(path)
        self.assertEqual(pinned, [{"pattern": "Disk *", "warning": 70, "critical": 80}])

    def test_missing_required_key_raises(self):
        import tempfile
        from axonopscli.application import Application

        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_policy(tmp, {
                "pinned_thresholds": [
                    {"pattern": "Disk *", "warning": 70},  # missing 'critical'
                ],
            })
            with self.assertRaises(ValueError) as ctx:
                Application._load_policy_file(path)
            self.assertIn("critical", str(ctx.exception))

    def test_non_object_top_level_raises(self):
        import tempfile
        from axonopscli.application import Application

        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_policy(tmp, "[]")
            with self.assertRaises(ValueError) as ctx:
                Application._load_policy_file(path)
            self.assertIn("JSON object", str(ctx.exception))

    def test_malformed_json_raises(self):
        import tempfile
        from axonopscli.application import Application

        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_policy(tmp, "{not json")
            with self.assertRaises(ValueError) as ctx:
                Application._load_policy_file(path)
            self.assertIn("not valid JSON", str(ctx.exception))


class TestSetLabelOverrideEndToEnd(unittest.TestCase):
    """End-to-end: --set-label retargets the query but never the stored expr."""

    def _input(self):
        return {
            "name": "demo",
            "metricrules": [{
                "id": "r1",
                "alert": "Keyspace Read Latency",
                "expr": "cas_Keyspace_ReadLatency{keyspace=~'system,myks'} >= 250",
                "operator": ">=",
                "criticalValue": 300,
                "warningValue": 250,
                "filters": [],
                "annotations": {},
                "integrations": {},
            }],
        }

    def test_query_uses_override_but_output_keeps_original_selector(self):
        config = _default_config(
            min_samples=5,
            max_delta=100.0,
            set_labels=[(None, "keyspace", "myks")],
        )
        axonops = MagicMock()
        axonops.get_cluster_type.return_value = "cassandra"
        orch = TuneAlertsOrchestrator(axonops, _args(org="acme", cluster="demo"), config)

        queried = []

        def fake_query(self, promql, start, end, step="1m"):
            queried.append(promql)
            # Only the OVERRIDDEN selector returns data; the original comma
            # list would return nothing (mirrors the real metrics API).
            if promql == "cas_Keyspace_ReadLatency{keyspace='myks'}":
                return list(range(1000))
            return []

        with patch.object(MetricQuerier, "query", new=fake_query):
            result = orch.tune_all(self._input())

        # It tuned — proving the query hit the overridden selector.
        outcome = result.outcomes[0]
        self.assertEqual(outcome.status, "tuned")
        self.assertEqual(queried, ["cas_Keyspace_ReadLatency{keyspace='myks'}"])

        # The stored expr keeps the ORIGINAL comma-list selector; only the
        # trailing threshold is rewritten.
        out_expr = result.tuned_json["metricrules"][0]["expr"]
        self.assertIn("keyspace=~'system,myks'", out_expr)
        self.assertNotIn("keyspace='myks'", out_expr)


if __name__ == "__main__":
    unittest.main()
