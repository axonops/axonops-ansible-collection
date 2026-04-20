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


if __name__ == "__main__":
    unittest.main()
