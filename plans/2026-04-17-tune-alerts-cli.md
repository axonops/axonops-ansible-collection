# Tune-Alerts CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `axonopscli tune-alerts` subcommand that reads an exported `alert_rules.json`, queries 7 days of metrics from `/api/v1/query_range`, and writes a tuned sibling JSON plus a markdown audit report. Thresholds calibrated to observed percentiles + configurable headroom.

**Architecture:** New file `cli/axonopscli/components/tune_alerts.py` with four focused classes — `ThresholdCalculator` (pure percentile math), `ExprRewriter` (pure expr string manipulation), `MetricQuerier` (HTTP wrapper), `TuneAlertsOrchestrator` (coordinates + writes JSON + audit report). Wired into `application.py` as a new subparser. Stacked on the existing `alerts-export-cli` branch.

**Tech Stack:** Python 3 stdlib only (`statistics`, `fnmatch`, `datetime`, `json`, `os`, `re`, `dataclasses`, `argparse`). `requests` already a runtime dep. `unittest` + `unittest.mock` for tests.

**Spec:** `plans/2026-04-17-tune-alerts-cli-design.md` (commit `4ca6282`)

**Branch:** `alerts-export-cli` (stacked — do NOT create a new branch)

---

## Pre-flight

- [ ] **Step 0.1: Verify branch and clean state**

```bash
cd /opt/repos/axonops-ansible-collection
git status
git branch --show-current
git log --oneline -3
```

Expected: branch is `alerts-export-cli`, working tree clean, most recent commit is `4ca6282 docs(plans): design for tune-alerts CLI subcommand`.

- [ ] **Step 0.2: Verify test baseline unchanged**

```bash
cd /opt/repos/axonops-ansible-collection/cli
python3 -m unittest discover -s tests 2>&1 | tail -3
```

Expected: `Ran 52 tests` with 3 pre-existing `test_get_jwt` errors (same `do_login` AttributeError present on `main`). Do NOT fix — out of scope.

- [ ] **Step 0.3: Re-read the spec**

Read `plans/2026-04-17-tune-alerts-cli-design.md` end-to-end to internalize decisions before starting.

---

## Task 1: ThresholdCalculator (Commit 1 of 8)

**Goal:** Pure function that given a list of numeric samples, an operator, and a profile config, returns new warning/critical thresholds. Direction-aware. No I/O. Heavy test target.

**Files:**

- Create: `cli/axonopscli/components/tune_alerts.py`
- Create: `cli/tests/test_tune_alerts_unittest.py`

### Step 1.1: Write the first failing test (p99 + 20% headroom, `>=` operator)

- [ ] Create `cli/tests/test_tune_alerts_unittest.py`:

```python
import unittest

from axonopscli.components.tune_alerts import ThresholdCalculator, TuneResult


class TestThresholdCalculator(unittest.TestCase):

    def test_p99_with_20pct_headroom_for_ge_operator(self):
        # Generate 1000 samples from 0..999 so p99 = 990
        samples = list(range(1000))
        result = ThresholdCalculator.compute(
            samples=samples,
            operator=">=",
            percentile=99.0,
            warning_headroom=0.10,
            critical_headroom=0.20,
        )
        # p99 of [0..999] is 990 (linear interpolation)
        self.assertAlmostEqual(result.percentile_value, 990.0, places=1)
        # warning = 990 * 1.10 = 1089
        self.assertAlmostEqual(result.new_warning, 1089.0, places=1)
        # critical = 990 * 1.20 = 1188
        self.assertAlmostEqual(result.new_critical, 1188.0, places=1)
        self.assertEqual(result.sample_count, 1000)


if __name__ == "__main__":
    unittest.main()
```

### Step 1.2: Run test to verify it fails

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection/cli
python3 -m unittest tests.test_tune_alerts_unittest -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'axonopscli.components.tune_alerts'`

### Step 1.3: Create `components/tune_alerts.py` with `TuneResult` dataclass and `ThresholdCalculator` — minimal happy path

- [ ] Create `cli/axonopscli/components/tune_alerts.py`:

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class TuneResult:
    """Outcome of ThresholdCalculator.compute() for a single rule."""
    new_warning: float
    new_critical: float
    percentile_value: float       # raw percentile value before headroom
    sample_count: int


class ThresholdCalculator:
    """Compute tuned warning/critical thresholds from observed samples.

    Pure; no I/O. Direction-aware: operators >= / > use upper percentile and
    positive headroom; operators <= / < use lower percentile and negative
    headroom. Caller is responsible for filtering None/NaN from samples.
    """

    @staticmethod
    def compute(
        samples: list,
        operator: str,
        percentile: float,
        warning_headroom: float,
        critical_headroom: float,
    ) -> TuneResult:
        if not samples:
            raise ValueError("compute() requires at least one sample")

        if operator in (">=", ">"):
            base = _percentile(samples, percentile)
            new_warning = base * (1.0 + warning_headroom)
            new_critical = base * (1.0 + critical_headroom)
        elif operator in ("<=", "<"):
            base = _percentile(samples, 100.0 - percentile)
            new_warning = base * (1.0 - warning_headroom)
            new_critical = base * (1.0 - critical_headroom)
        else:
            raise ValueError(f"Unsupported operator for tuning: {operator!r}")

        return TuneResult(
            new_warning=new_warning,
            new_critical=new_critical,
            percentile_value=base,
            sample_count=len(samples),
        )


def _percentile(samples: list, p: float) -> float:
    """Linear-interpolation percentile. p is in [0, 100]. Stdlib-only."""
    if not samples:
        raise ValueError("_percentile requires at least one sample")
    if not 0.0 <= p <= 100.0:
        raise ValueError(f"percentile must be in [0, 100], got {p}")
    sorted_samples = sorted(samples)
    n = len(sorted_samples)
    if n == 1:
        return float(sorted_samples[0])
    pos = (n - 1) * p / 100.0
    lower = int(pos)
    upper = min(lower + 1, n - 1)
    weight = pos - lower
    return sorted_samples[lower] * (1.0 - weight) + sorted_samples[upper] * weight
```

### Step 1.4: Run test to verify it passes

- [ ] Run:

```bash
python3 -m unittest tests.test_tune_alerts_unittest -v
```

Expected: 1 test passes.

### Step 1.5: Add the remaining `ThresholdCalculator` tests

- [ ] Append to `cli/tests/test_tune_alerts_unittest.py` inside `TestThresholdCalculator`:

```python
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
        self.assertAlmostEqual(result.new_warning, 990.0, places=1)
        self.assertAlmostEqual(result.new_critical, 990.0, places=1)

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
        # p99.9 of 0..9999 = 9990.01
        self.assertAlmostEqual(result.percentile_value, 9990.0, places=0)
```

### Step 1.6: Run all tests in the class

- [ ] Run:

```bash
python3 -m unittest tests.test_tune_alerts_unittest -v
```

Expected: 10 tests pass, 0 failures.

### Step 1.7: Commit

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection
git add cli/axonopscli/components/tune_alerts.py cli/tests/test_tune_alerts_unittest.py
git status --short   # confirm only those two files staged
git commit -m "$(cat <<'EOF'
feat(cli): add ThresholdCalculator for alert tuning

Pure helper for computing tuned warning/critical thresholds from
observed metric samples. Direction-aware: >=/> uses upper percentile
and positive headroom; </<= uses lower percentile and negative
headroom, preserving the "alert if it gets X% worse than last week"
semantic for either tail.

Caller supplies the samples list (pre-cleaned of nulls/NaN). Caller
is responsible for sanity clamps on the returned TuneResult (zero
values, unreasonable deltas) — this class just does the math.

Stdlib-only linear-interpolation percentile; no numpy dependency.
EOF
)"
```

---

## Task 2: ExprRewriter (Commit 2 of 8)

**Goal:** Pure helper that strips the trailing ` <operator> <value>` from an alert `expr` string and emits a new expr with the updated threshold. Uses the same pattern the existing `alert_rule.py` Ansible module uses.

**Files:**

- Modify: `cli/axonopscli/components/tune_alerts.py` (append class)
- Modify: `cli/tests/test_tune_alerts_unittest.py` (add test class)

### Step 2.1: Write failing tests

- [ ] Append to `cli/tests/test_tune_alerts_unittest.py` (after the `TestThresholdCalculator` class, before `if __name__`):

```python
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
```

### Step 2.2: Run tests to verify they fail

- [ ] Run:

```bash
python3 -m unittest tests.test_tune_alerts_unittest.TestExprRewriter -v
```

Expected: FAIL with `ImportError: cannot import name 'ExprRewriter'`

### Step 2.3: Implement `ExprRewriter`

- [ ] Append to `cli/axonopscli/components/tune_alerts.py` (after the `_percentile` helper):

```python
import re


# Pattern mirrors the stripping regex used by the existing Ansible
# alert_rule.py module (line ~253): expressions always end with
# ` <operator> <value>`.
_TRAILING_THRESHOLD_RE = re.compile(r'^(.*)\s(<=|>=|<|>|==|!=)\s(\S+)$')


class ExprRewriter:
    """Strip or replace the trailing `<op> <value>` on an alert expression.

    Pure; no I/O. If the expression doesn't match the expected shape,
    raises ValueError so the orchestrator can skip the rule with a
    clear reason.
    """

    @staticmethod
    def strip_threshold(expr: str) -> tuple:
        """Return (bare_metric, operator, old_value_str) or raise ValueError."""
        m = _TRAILING_THRESHOLD_RE.match(expr.strip())
        if not m:
            raise ValueError(f"Cannot parse trailing threshold from expr: {expr!r}")
        return m.group(1), m.group(2), m.group(3)

    @staticmethod
    def rewrite(expr: str, new_warning) -> str:
        """Return a new expr with the trailing value replaced by new_warning."""
        bare, op, _old = ExprRewriter.strip_threshold(expr)
        return f"{bare} {op} {_format_value(new_warning)}"


def _format_value(v) -> str:
    """Format a numeric threshold without a trailing `.0` when it's whole."""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)
```

### Step 2.4: Run tests to verify they pass

- [ ] Run:

```bash
python3 -m unittest tests.test_tune_alerts_unittest.TestExprRewriter -v
```

Expected: 8 tests pass.

### Step 2.5: Run full module

- [ ] Run:

```bash
python3 -m unittest tests.test_tune_alerts_unittest -v 2>&1 | tail -3
```

Expected: 18 tests pass, 0 failures.

### Step 2.6: Commit

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection
git add cli/axonopscli/components/tune_alerts.py cli/tests/test_tune_alerts_unittest.py
git status --short
git commit -m "$(cat <<'EOF'
feat(cli): add ExprRewriter for alert tuning

Pure helper that splits an alert expression on its trailing
`<operator> <value>` (the exact shape stored in AxonOps alert rules
and also relied upon by the existing alert_rule.py Ansible module)
and emits a replacement with a new threshold while preserving the
operator and the bare metric verbatim.

Whole-number floats are formatted without a trailing `.0` so the
rewritten JSON stays idiomatic (`>= 1089` rather than `>= 1089.0`).
EOF
)"
```

---

## Task 3: MetricQuerier (Commit 3 of 8)

**Goal:** Thin wrapper over `axonops.do_request` that queries `/api/v1/query_range` and returns a flat list of numeric samples.

**URL shape note:** The spec assumes `/api/v1/query_range/{org}/{cluster_type}/{cluster}` mirroring the `alert-rules` endpoint. This is the most likely shape but hasn't been verified against the live API. If Step 3.6 smoke-test fails with a 404, adjust `QUERY_RANGE_URL` to the no-path form `/api/v1/query_range` and re-run.

**Files:**

- Modify: `cli/axonopscli/components/tune_alerts.py` (append class)
- Modify: `cli/tests/test_tune_alerts_unittest.py` (add test class)

### Step 3.1: Write failing tests

- [ ] Append to `cli/tests/test_tune_alerts_unittest.py`:

```python
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
```

### Step 3.2: Run tests to verify they fail

- [ ] Run:

```bash
python3 -m unittest tests.test_tune_alerts_unittest.TestMetricQuerier -v
```

Expected: FAIL with `ImportError: cannot import name 'MetricQuerier'`

### Step 3.3: Implement `MetricQuerier`

- [ ] Append to `cli/axonopscli/components/tune_alerts.py`:

```python
import math
import urllib.parse


class MetricQuerier:
    """Query /api/v1/query_range and return a flat list of numeric samples."""

    QUERY_RANGE_URL = "/api/v1/query_range/{org}/{cluster_type}/{cluster}"

    def __init__(self, axonops, args):
        self.axonops = axonops
        self.args = args

    def query(self, promql: str, start: int, end: int, step: str = "1m") -> list:
        """Return a flat list of non-null, finite, float samples across all series.

        start/end are Unix epoch seconds. step is a Prometheus duration string
        (e.g. '1m', '15s'). Raises HTTPCodeError on transport/server failure.
        """
        path = self.QUERY_RANGE_URL.format(
            org=self.args.org,
            cluster_type=self.axonops.get_cluster_type(),
            cluster=self.args.cluster,
        )
        qs = urllib.parse.urlencode({
            "query": promql,
            "start": start,
            "end": end,
            "step": step,
        })
        url = f"{path}?{qs}"
        response = self.axonops.do_request(url=url, method="GET")
        return self._flatten(response)

    @staticmethod
    def _flatten(response: dict) -> list:
        if not response:
            return []
        data = response.get("data") or {}
        result = data.get("result") or []
        out = []
        for series in result:
            for point in series.get("values") or []:
                # point is [timestamp, value_string_or_null]
                if len(point) != 2:
                    continue
                value_raw = point[1]
                if value_raw is None:
                    continue
                try:
                    value = float(value_raw)
                except (TypeError, ValueError):
                    continue
                if math.isnan(value) or math.isinf(value):
                    continue
                out.append(value)
        return out
```

### Step 3.4: Run tests to verify they pass

- [ ] Run:

```bash
python3 -m unittest tests.test_tune_alerts_unittest.TestMetricQuerier -v
```

Expected: 5 tests pass.

### Step 3.5: Run full module

- [ ] Run:

```bash
python3 -m unittest tests.test_tune_alerts_unittest -v 2>&1 | tail -3
```

Expected: 23 tests pass (10 calc + 8 expr + 5 querier).

### Step 3.6: Empirical URL verification (optional but recommended)

If you have live AxonOps credentials for a small throwaway query, verify the URL template against a real cluster. This catches a 404 BEFORE Task 4 depends on it.

- [ ] Run (only if you have an AXONOPS_TOKEN and cluster to test against):

```bash
cd /opt/repos/axonops-ansible-collection/cli
python3 -c "
from axonopscli.axonops import AxonOps
from axonopscli.components.tune_alerts import MetricQuerier
from types import SimpleNamespace
import os

ax = AxonOps(org_name=os.environ['AXONOPS_ORG'], api_token=os.environ['AXONOPS_TOKEN'], cluster_type='cassandra')
q = MetricQuerier(ax, SimpleNamespace(org=os.environ['AXONOPS_ORG'], cluster=os.environ['AXONOPS_CLUSTER'], v=0))

import time
end = int(time.time())
start = end - 300  # last 5 minutes
samples = q.query('up', start=start, end=end, step='1m')
print(f'Got {len(samples)} samples from {end-start}s window')
print(f'Sample values: {samples[:10]}')
"
```

Expected: prints a small number of samples without error. If you see `HTTPCodeError: ... returned 404`, the URL template is wrong — edit `QUERY_RANGE_URL` in `tune_alerts.py` to `/api/v1/query_range` (no org/cluster path) and retry. Update Step 3.1 test assertions to match if the template changes.

### Step 3.7: Commit

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection
git add cli/axonopscli/components/tune_alerts.py cli/tests/test_tune_alerts_unittest.py
git status --short
git commit -m "$(cat <<'EOF'
feat(cli): add MetricQuerier for /api/v1/query_range

Thin wrapper over AxonOps.do_request that hits the Prometheus-
compatible query_range endpoint and flattens the matrix response
(list of series, each with [timestamp, value] pairs) into a single
flat list of numeric samples. Drops nulls, NaN, and infinities so
the downstream percentile calculation receives pre-cleaned input.

URL template mirrors the alert-rules endpoint:
  /api/v1/query_range/{org}/{cluster_type}/{cluster}

If the AxonOps server exposes this endpoint at a different path
(e.g. without org/cluster embedded), adjust QUERY_RANGE_URL and
the corresponding test.
EOF
)"
```

---

## Task 4: TuneAlertsOrchestrator (Commit 4 of 8)

**Goal:** Coordinates everything: reads input JSON, iterates rules, applies filters, calls the three helpers, applies sanity clamps, writes JSON and the sidecar markdown report, prints the stdout summary.

This is the largest task. It's split into logical sub-sections — one TDD mini-cycle per section, ending in a single commit covering all.

**Files:**

- Modify: `cli/axonopscli/components/tune_alerts.py` (append data classes + orchestrator)
- Modify: `cli/tests/test_tune_alerts_unittest.py` (add test classes)

### Step 4.1: Write failing tests for the filter logic

- [ ] Append to `cli/tests/test_tune_alerts_unittest.py`:

```python
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
```

### Step 4.2: Run tests — verify fail

- [ ] Run:

```bash
python3 -m unittest tests.test_tune_alerts_unittest.TestRuleFilter -v
```

Expected: FAIL with `ImportError: cannot import name 'RuleFilter'`

### Step 4.3: Implement `RuleFilter`

- [ ] Append to `cli/axonopscli/components/tune_alerts.py`:

```python
import fnmatch


class RuleFilter:
    """Decide whether a given rule name passes the user's include/exclude/rules filters.

    Semantics:
      - If `rules` is non-empty: only rules whose name exactly matches one of those strings pass
        the include check (acts as a whitelist). If `include` is also set, both apply (AND).
      - If `include` is non-empty (and `rules` is empty): rule name must match at least one glob.
      - If `exclude` is non-empty: rule name must NOT match any exclude glob. exclude wins over include.
      - All three empty: accept everything.
    """

    def __init__(self, include: list, exclude: list, rules: list):
        self.include = list(include or [])
        self.exclude = list(exclude or [])
        self.rules = list(rules or [])

    def accepts(self, rule_name: str) -> bool:
        # exclude first — it's a hard veto
        for pat in self.exclude:
            if fnmatch.fnmatchcase(rule_name, pat):
                return False
        # if --rule is specified, it's a whitelist
        if self.rules:
            if rule_name not in self.rules:
                return False
        # if --include specified, must match at least one
        if self.include:
            return any(fnmatch.fnmatchcase(rule_name, pat) for pat in self.include)
        return True
```

### Step 4.4: Run filter tests — verify pass

- [ ] Run:

```bash
python3 -m unittest tests.test_tune_alerts_unittest.TestRuleFilter -v
```

Expected: 6 tests pass.

### Step 4.5: Write failing tests for `TuneAlertsOrchestrator` happy path + skip reasons

- [ ] Append to `cli/tests/test_tune_alerts_unittest.py`:

```python
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
        max_delta=10.0,
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
            # p99 = 990, critical headroom 0.20 => ~1188
            self.assertAlmostEqual(outcome.new_critical, 1188.0, places=0)

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
        orch = self._make_orch({
            "jvm_gc_CollectionTime": list(range(10)),  # p99 ≈ 9, *1.20 = 10.8
            "abs(host_ntp_offset_seconds) * 1000": list(range(10)),
        })
        with patch.object(MetricQuerier, 'query', new=orch._fake_query):
            result = orch.tune_all(_sample_input())

        o = {o.rule_name: o for o in result.outcomes}
        # Both rules will hit min_samples first (len=10 < min=100); override:
        config = _default_config(min_samples=5)
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
        self.assertAlmostEqual(rule["warningValue"], 1089.0, places=0)
        self.assertAlmostEqual(rule["criticalValue"], 1188.0, places=0)
        # expr must carry the new warning threshold (not the critical)
        self.assertTrue(
            rule["expr"].endswith(" >= 1089"),
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
```

### Step 4.6: Run tests — verify fail

- [ ] Run:

```bash
python3 -m unittest tests.test_tune_alerts_unittest.TestTuneAlertsOrchestrator -v
```

Expected: FAIL with `ImportError: cannot import name 'TuneAlertsOrchestrator'`

### Step 4.7: Implement `TuneAlertsConfig`, `RuleOutcome`, `TuneRunResult`, and `TuneAlertsOrchestrator`

- [ ] Append to `cli/axonopscli/components/tune_alerts.py`:

```python
import time
from copy import deepcopy


@dataclass
class TuneAlertsConfig:
    profile: str                    # "noisy" | "default" | "quiet"
    percentile: float
    warning_headroom: float
    critical_headroom: float
    min_samples: int
    max_delta: float
    include: list
    exclude: list
    rules: list


@dataclass
class RuleOutcome:
    rule_name: str
    status: str                     # "tuned" | "skipped" | "filtered"
    reason: Optional[str] = None    # populated for skipped/filtered
    old_warning: Optional[float] = None
    old_critical: Optional[float] = None
    new_warning: Optional[float] = None
    new_critical: Optional[float] = None
    percentile_value: Optional[float] = None
    sample_count: Optional[int] = None
    operator: Optional[str] = None


@dataclass
class TuneRunResult:
    cluster_name: str
    window_start: int               # Unix epoch seconds
    window_end: int
    profile: str
    percentile: float
    warning_headroom: float
    critical_headroom: float
    outcomes: list                  # list[RuleOutcome]
    tuned_json: dict                # the full JSON with in-place updates

    @property
    def tuned_count(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "tuned")

    @property
    def skipped_count(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "skipped")

    @property
    def filtered_count(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "filtered")


class TuneAlertsOrchestrator:
    """Orchestrate the full tune-alerts run for one cluster.

    Does not do I/O itself beyond invoking MetricQuerier; the caller
    is responsible for reading/writing files using load_input() /
    write_output() / write_audit_report() / print_summary().
    """

    SEVEN_DAYS_SECS = 7 * 24 * 60 * 60

    def __init__(self, axonops, args, config: TuneAlertsConfig):
        self.axonops = axonops
        self.args = args
        self.config = config
        self.filter = RuleFilter(
            include=config.include,
            exclude=config.exclude,
            rules=config.rules,
        )

    # ---- file I/O (called by run_tune_alerts in application.py) ----

    def load_input(self, path: str) -> dict:
        """Read and validate the input JSON."""
        with open(path, "r") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Input JSON must be an object, got {type(data).__name__}")
        if "metricrules" not in data or not isinstance(data["metricrules"], list):
            raise ValueError("Input JSON missing 'metricrules' list")
        return data

    # ---- main orchestration ----

    def tune_all(self, input_json: dict) -> TuneRunResult:
        cluster_name = input_json.get("name") or self.args.cluster
        tuned_json = deepcopy(input_json)

        end_ts = int(time.time())
        start_ts = end_ts - self.SEVEN_DAYS_SECS

        outcomes = []
        for rule in tuned_json["metricrules"]:
            outcome = self._tune_one(rule, start_ts, end_ts)
            outcomes.append(outcome)

        return TuneRunResult(
            cluster_name=cluster_name,
            window_start=start_ts,
            window_end=end_ts,
            profile=self.config.profile,
            percentile=self.config.percentile,
            warning_headroom=self.config.warning_headroom,
            critical_headroom=self.config.critical_headroom,
            outcomes=outcomes,
            tuned_json=tuned_json,
        )

    def _tune_one(self, rule: dict, start_ts: int, end_ts: int) -> RuleOutcome:
        from axonopscli.utils import HTTPCodeError

        name = rule.get("alert", "<unnamed>")
        expr = rule.get("expr", "")
        old_warning = rule.get("warningValue")
        old_critical = rule.get("criticalValue")

        # Filter stage
        if not self.filter.accepts(name):
            return RuleOutcome(
                rule_name=name, status="filtered", reason="excluded by filter",
                old_warning=old_warning, old_critical=old_critical,
            )

        # Parse expr
        try:
            bare, operator, _old_str = ExprRewriter.strip_threshold(expr)
        except ValueError as e:
            return RuleOutcome(
                rule_name=name, status="skipped", reason=f"cannot parse expr: {e}",
                old_warning=old_warning, old_critical=old_critical,
            )

        # Query samples
        querier = MetricQuerier(self.axonops, self.args)
        try:
            samples = querier.query(bare, start=start_ts, end=end_ts, step="1m")
        except HTTPCodeError as e:
            return RuleOutcome(
                rule_name=name, status="skipped",
                reason=f"query failed: {e}",
                old_warning=old_warning, old_critical=old_critical,
                operator=operator,
            )

        if len(samples) < self.config.min_samples:
            return RuleOutcome(
                rule_name=name, status="skipped",
                reason=f"insufficient data ({len(samples)} samples)",
                old_warning=old_warning, old_critical=old_critical,
                operator=operator,
                sample_count=len(samples),
            )

        # Compute thresholds
        try:
            calc = ThresholdCalculator.compute(
                samples=samples,
                operator=operator,
                percentile=self.config.percentile,
                warning_headroom=self.config.warning_headroom,
                critical_headroom=self.config.critical_headroom,
            )
        except ValueError as e:
            return RuleOutcome(
                rule_name=name, status="skipped", reason=f"threshold compute error: {e}",
                old_warning=old_warning, old_critical=old_critical, operator=operator,
            )

        # Sanity clamps
        if calc.new_warning <= 0 or calc.new_critical <= 0:
            return RuleOutcome(
                rule_name=name, status="skipped",
                reason=f"nonsensical (new warning={calc.new_warning}, critical={calc.new_critical})",
                old_warning=old_warning, old_critical=old_critical, operator=operator,
                sample_count=calc.sample_count,
            )

        if self._unreasonable_delta(old_warning, calc.new_warning) or \
           self._unreasonable_delta(old_critical, calc.new_critical):
            return RuleOutcome(
                rule_name=name, status="skipped",
                reason=f"unreasonable delta (max_delta={self.config.max_delta})",
                old_warning=old_warning, old_critical=old_critical,
                new_warning=calc.new_warning, new_critical=calc.new_critical,
                operator=operator, sample_count=calc.sample_count,
                percentile_value=calc.percentile_value,
            )

        # Apply
        rule["warningValue"] = _round_threshold(calc.new_warning)
        rule["criticalValue"] = _round_threshold(calc.new_critical)
        rule["expr"] = ExprRewriter.rewrite(expr, new_warning=rule["warningValue"])

        return RuleOutcome(
            rule_name=name, status="tuned",
            old_warning=old_warning, old_critical=old_critical,
            new_warning=rule["warningValue"], new_critical=rule["criticalValue"],
            operator=operator,
            sample_count=calc.sample_count,
            percentile_value=calc.percentile_value,
        )

    def _unreasonable_delta(self, old_val, new_val) -> bool:
        try:
            old_f = float(old_val)
            new_f = float(new_val)
        except (TypeError, ValueError):
            return False
        if old_f == 0:
            return False
        ratio = max(abs(new_f / old_f), abs(old_f / new_f))
        return ratio > self.config.max_delta


def _round_threshold(v: float):
    """Round to int if whole, else 2 decimals. Keeps JSON idiomatic."""
    rounded = round(v, 2)
    if rounded == int(rounded):
        return int(rounded)
    return rounded
```

### Step 4.8: Run orchestrator tests — verify pass

- [ ] Run:

```bash
python3 -m unittest tests.test_tune_alerts_unittest.TestTuneAlertsOrchestrator -v
```

Expected: 7 tests pass.

### Step 4.9: Write failing tests for output writers

- [ ] Append to `cli/tests/test_tune_alerts_unittest.py`:

```python
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
```

### Step 4.10: Run output tests — verify fail

- [ ] Run:

```bash
python3 -m unittest tests.test_tune_alerts_unittest.TestTuneAlertsOrchestratorOutput -v
```

Expected: FAIL with `AttributeError: 'TuneAlertsOrchestrator' object has no attribute 'write_output'`

### Step 4.11: Implement output writers and summary

- [ ] Append to the `TuneAlertsOrchestrator` class in `cli/axonopscli/components/tune_alerts.py` (inside the class):

```python
    # ---- output writers ----

    def write_output(self, input_path: str, result: TuneRunResult) -> str:
        """Write the tuned JSON sibling file. Returns the output path."""
        out_path = self._output_json_path(input_path, result.cluster_name)
        # Atomic creation with restrictive mode
        if os.path.exists(out_path):
            os.chmod(out_path, 0o600)
        fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(result.tuned_json, f, indent=4)
        return out_path

    def write_audit_report(self, input_path: str, result: TuneRunResult) -> str:
        """Write the sidecar markdown audit report. Returns the report path."""
        out_path = self._output_report_path(input_path, result.cluster_name)
        content = self._render_audit_report(input_path, result)
        with open(out_path, "w") as f:
            f.write(content)
        os.chmod(out_path, 0o644)
        return out_path

    def print_summary(self, result: TuneRunResult, json_path: str) -> None:
        summary_parts = [f"Tuned {result.tuned_count}"]
        if result.skipped_count:
            reasons = {}
            for o in result.outcomes:
                if o.status == "skipped":
                    # Bucket by the first word of the reason
                    key = (o.reason or "unknown").split("(")[0].strip()
                    reasons[key] = reasons.get(key, 0) + 1
            parts = ", ".join(f"{k}: {v}" for k, v in sorted(reasons.items()))
            summary_parts.append(f"skipped {result.skipped_count} ({parts})")
        if result.filtered_count:
            summary_parts.append(f"filtered {result.filtered_count}")
        summary_parts.append(f"wrote {json_path}")
        print(", ".join(summary_parts))

        if self.args.v:
            for o in result.outcomes:
                self._print_verbose(o)

    def _print_verbose(self, o: RuleOutcome) -> None:
        if o.status == "tuned":
            print(
                f"  [tuned]    {o.rule_name}: "
                f"warning {o.old_warning}→{o.new_warning}, "
                f"critical {o.old_critical}→{o.new_critical}, "
                f"p{self.config.percentile}={_format_value(o.percentile_value)}, "
                f"{o.sample_count} samples"
            )
        elif o.status == "skipped":
            print(f"  [skipped]  {o.rule_name}: {o.reason}")
        elif o.status == "filtered":
            print(f"  [filtered] {o.rule_name}: {o.reason}")

    # ---- path helpers ----

    def _output_json_path(self, input_path: str, cluster_name: str) -> str:
        return os.path.join(
            os.path.dirname(os.path.abspath(input_path)),
            f"alert_rules.tuned.for.{cluster_name}.json",
        )

    def _output_report_path(self, input_path: str, cluster_name: str) -> str:
        return os.path.join(
            os.path.dirname(os.path.abspath(input_path)),
            f"alert_rules.tuned.for.{cluster_name}.report.md",
        )

    # ---- audit report rendering ----

    def _render_audit_report(self, input_path: str, result: TuneRunResult) -> str:
        from datetime import datetime, timezone

        gen_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        window_start = datetime.fromtimestamp(result.window_start, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        window_end = datetime.fromtimestamp(result.window_end, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        lines = [
            f"# Alert tuning report — {result.cluster_name}",
            "",
            f"**Generated:** {gen_ts}",
            f"**Source:** {input_path}",
            f"**Profile:** {result.profile} "
            f"(p{result.percentile}, warning +{int(result.warning_headroom * 100)}%, "
            f"critical +{int(result.critical_headroom * 100)}%)",
            f"**Window:** {window_start} → {window_end} (7 days)",
            "",
            "## Summary",
            "",
            f"- Tuned: {result.tuned_count} rules",
            f"- Skipped: {result.skipped_count} rules",
            f"- Filtered out: {result.filtered_count} rules",
            "",
        ]

        tuned = [o for o in result.outcomes if o.status == "tuned"]
        if tuned:
            lines.extend([
                "## Tuned rules",
                "",
                "| Rule | Op | warning (old → new) | critical (old → new) | percentile value | Samples |",
                "|---|---|---|---|---|---|",
            ])
            for o in tuned:
                lines.append(
                    f"| {o.rule_name} | {o.operator} | "
                    f"{o.old_warning} → {o.new_warning} | "
                    f"{o.old_critical} → {o.new_critical} | "
                    f"{_format_value(o.percentile_value)} | {o.sample_count} |"
                )
            lines.append("")

        skipped = [o for o in result.outcomes if o.status == "skipped"]
        if skipped:
            lines.extend(["## Skipped rules", "", "| Rule | Reason |", "|---|---|"])
            for o in skipped:
                lines.append(f"| {o.rule_name} | {o.reason} |")
            lines.append("")

        filtered = [o for o in result.outcomes if o.status == "filtered"]
        if filtered:
            lines.extend(["## Filtered rules", "", "| Rule | Reason |", "|---|---|"])
            for o in filtered:
                lines.append(f"| {o.rule_name} | {o.reason} |")
            lines.append("")

        return "\n".join(lines)
```

### Step 4.12: Run output tests — verify pass

- [ ] Run:

```bash
python3 -m unittest tests.test_tune_alerts_unittest.TestTuneAlertsOrchestratorOutput -v
```

Expected: 6 tests pass.

### Step 4.13: Run full module

- [ ] Run:

```bash
python3 -m unittest tests.test_tune_alerts_unittest -v 2>&1 | tail -3
```

Expected: 10 + 8 + 5 + 6 + 7 + 6 = 42 tests pass.

### Step 4.14: Commit

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection
git add cli/axonopscli/components/tune_alerts.py cli/tests/test_tune_alerts_unittest.py
git status --short
git commit -m "$(cat <<'EOF'
feat(cli): add TuneAlertsOrchestrator

Coordinates the full tune-alerts run: reads the input JSON, applies
include/exclude/rule filters, queries each rule's metric for the
last 7 days, computes tuned thresholds, applies sanity clamps (hard
floor at ≤0, soft ratio clamp via max_delta), rewrites each rule's
warningValue/criticalValue/expr, and writes both the tuned sibling
JSON (mode 0600) and a sidecar markdown audit report (mode 0644)
for human review before re-apply.

The stdout summary is always printed; -v enables per-rule detail
so operators can see exactly why each rule was tuned, skipped, or
filtered. Filenames follow the `alert_rules.tuned.for.<cluster>`
convention specified in the design.
EOF
)"
```

---

## Task 5: Wire `tune-alerts` CLI subcommand (Commit 5 of 8)

**Goal:** Add argparse subparser and `run_tune_alerts` handler to `application.py`; add end-to-end tests.

**Files:**

- Modify: `cli/axonopscli/application.py`
- Modify: `cli/tests/test_tune_alerts_unittest.py`

### Step 5.1: Write failing end-to-end test

- [ ] Append to `cli/tests/test_tune_alerts_unittest.py`:

```python
class TestApplicationRunTuneAlerts(unittest.TestCase):

    def test_application_run_tune_alerts_end_to_end(self):
        from axonopscli.application import Application
        from axonopscli.axonops import AxonOps

        with tempfile.TemporaryDirectory() as tmp:
            # Write an input alert_rules.json
            input_path = os.path.join(tmp, "alert_rules.json")
            with open(input_path, "w") as f:
                json.dump(_sample_input(cluster_name="bc1"), f)

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
                    "--org", "acme", "--cluster", "bc1", "--token", "t",
                    "tune-alerts", "--input", input_path,
                ])

            # Verify output files exist
            self.assertTrue(os.path.exists(os.path.join(tmp, "alert_rules.tuned.for.bc1.json")))
            self.assertTrue(os.path.exists(os.path.join(tmp, "alert_rules.tuned.for.bc1.report.md")))

    def test_application_run_tune_alerts_profile_quiet(self):
        from axonopscli.application import Application
        from axonopscli.axonops import AxonOps

        with tempfile.TemporaryDirectory() as tmp:
            input_path = os.path.join(tmp, "alert_rules.json")
            with open(input_path, "w") as f:
                json.dump(_sample_input(cluster_name="bc1"), f)

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
                    "--org", "acme", "--cluster", "bc1", "--token", "t",
                    "tune-alerts", "--input", input_path, "--profile", "quiet",
                ])

            out_path = os.path.join(tmp, "alert_rules.tuned.for.bc1.json")
            with open(out_path) as f:
                out = json.load(f)
            # Quiet profile: p99.9 + 50% critical headroom on 1000 samples → p99.9 ≈ 999, critical ≈ 1498.5
            self.assertGreater(out["metricrules"][0]["criticalValue"], 1400)
```

### Step 5.2: Run test — verify fail

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection/cli
python3 -m unittest tests.test_tune_alerts_unittest.TestApplicationRunTuneAlerts -v
```

Expected: FAIL — argparse error or SystemExit because `tune-alerts` doesn't exist.

### Step 5.3: Add the subparser block in `application.py`

- [ ] Open `cli/axonopscli/application.py`. Find the `alerts_parser` block (around the end of the `run` method, just before `parsed_result = parser.parse_args(...)`). Immediately after the `alerts_parser.add_argument('--include-secrets', ...)` block, insert:

```python
        tune_alerts_parser = commands_subparser.add_parser(
            "tune-alerts",
            help="Tune existing alert rule thresholds against the last 7 days of observed metrics")

        tune_alerts_parser.set_defaults(func=self.run_tune_alerts)

        tune_alerts_parser.add_argument('--input', type=str, required=True,
                                        help='Path to alert_rules.json exported by the alerts subcommand')
        tune_alerts_parser.add_argument('--profile', type=str, default='default',
                                        choices=['noisy', 'default', 'quiet'],
                                        help='Preset: noisy=p95/5%%-10%%, default=p99/10%%-20%%, quiet=p99.9/20%%-50%%')
        tune_alerts_parser.add_argument('--percentile', type=float, default=None,
                                        help='Override profile percentile (0 < P < 100)')
        tune_alerts_parser.add_argument('--warning-headroom', type=float, default=None,
                                        help='Override profile warning headroom (e.g. 0.10 = +10%%)')
        tune_alerts_parser.add_argument('--critical-headroom', type=float, default=None,
                                        help='Override profile critical headroom (e.g. 0.20 = +20%%)')
        tune_alerts_parser.add_argument('--min-samples', type=int, default=100,
                                        help='Skip rules with fewer samples than this (default 100)')
        tune_alerts_parser.add_argument('--max-delta', type=float, default=10.0,
                                        help='Skip rules whose new threshold differs from original by more than this multiple (default 10)')
        tune_alerts_parser.add_argument('--include', action='append', default=[],
                                        help='Include rules matching this glob (repeatable)')
        tune_alerts_parser.add_argument('--exclude', action='append', default=[],
                                        help='Exclude rules matching this glob (repeatable; overrides --include)')
        tune_alerts_parser.add_argument('--rule', action='append', default=[],
                                        help='Tune only this exact rule name (repeatable)')
```

### Step 5.4: Add the run handler

- [ ] Add a new method to the `Application` class in `cli/axonopscli/application.py` (after `run_alerts`):

```python
    def run_tune_alerts(self, args: argparse.Namespace):
        """ Run the alerts tuning """
        if args.v:
            print(f"Running alerts tuning on {args.org}/{args.cluster}")
            print(_scrubbed_args(args))

        axonops = self.get_axonops(args)

        from .components.tune_alerts import TuneAlertsOrchestrator, TuneAlertsConfig

        config = self._build_tune_alerts_config(args)
        orchestrator = TuneAlertsOrchestrator(axonops, args, config)

        input_json = orchestrator.load_input(args.input)
        result = orchestrator.tune_all(input_json)
        json_path = orchestrator.write_output(args.input, result)
        orchestrator.write_audit_report(args.input, result)
        orchestrator.print_summary(result, json_path)

    @staticmethod
    def _build_tune_alerts_config(args):
        from .components.tune_alerts import TuneAlertsConfig

        # Profile presets
        presets = {
            'noisy':   (95.0,  0.05, 0.10),
            'default': (99.0,  0.10, 0.20),
            'quiet':   (99.9,  0.20, 0.50),
        }
        p_percentile, p_warn, p_crit = presets[args.profile]

        return TuneAlertsConfig(
            profile=args.profile,
            percentile=args.percentile if args.percentile is not None else p_percentile,
            warning_headroom=args.warning_headroom if args.warning_headroom is not None else p_warn,
            critical_headroom=args.critical_headroom if args.critical_headroom is not None else p_crit,
            min_samples=args.min_samples,
            max_delta=args.max_delta,
            include=list(args.include or []),
            exclude=list(args.exclude or []),
            rules=list(args.rule or []),
        )
```

### Step 5.5: Run end-to-end tests — verify pass

- [ ] Run:

```bash
python3 -m unittest tests.test_tune_alerts_unittest.TestApplicationRunTuneAlerts -v
```

Expected: 2 tests pass.

### Step 5.6: Smoke-test the CLI help

- [ ] Run:

```bash
python3 -c "from axonopscli.application import Application; Application().run(['tune-alerts', '--help'])" 2>&1 | head -30
```

Expected: argparse help listing `--input` (required), `--profile`, `--percentile`, `--warning-headroom`, `--critical-headroom`, `--min-samples`, `--max-delta`, `--include`, `--exclude`, `--rule`.

### Step 5.7: Run the full alerts test suite to verify no regressions

- [ ] Run:

```bash
python3 -m unittest discover -s tests 2>&1 | tail -3
```

Expected: 52 (pre-existing) + 42 (tune-alerts) + 2 (e2e) = 96 tests run; 3 pre-existing `test_get_jwt` errors unchanged; all new tests pass.

### Step 5.8: Commit

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection
git add cli/axonopscli/application.py cli/tests/test_tune_alerts_unittest.py
git status --short
git commit -m "$(cat <<'EOF'
feat(cli): wire tune-alerts CLI subcommand

Adds the `tune-alerts` subparser + run_tune_alerts handler. Profile
presets (noisy/default/quiet) map to (percentile, warning-headroom,
critical-headroom) tuples; individual CLI flags override any field
of the chosen profile.

End-to-end tests patch AxonOps.do_request with canned Prometheus
matrix responses to exercise the full path: parse input JSON →
query → tune → write sibling JSON + audit report.
EOF
)"
```

---

## Task 6: Documentation (Commit 6 of 8)

**Goal:** Add a `tune-alerts` section to `cli/README.md`.

**Files:**

- Modify: `cli/README.md`

### Step 6.1: Append the tune-alerts section

- [ ] Append to `cli/README.md` (after the existing `alerts` section, which is at the end of the file):

```markdown

### `tune-alerts` Subcommand

Read an existing `alert_rules.json` (produced by the `alerts` subcommand or
hand-crafted in the same shape) and write a tuned sibling JSON whose
`warningValue` and `criticalValue` are calibrated to the last 7 days of
observed metric data. Companion markdown audit report lists every change
with before/after/percentile/sample count, so you can review the tuning
before re-applying.

#### Options:

* `--input` (required) Path to the source `alert_rules.json`. The tuned
  output is written alongside it as `alert_rules.tuned.for.<cluster>.json`
  plus a `<...>.report.md`.
* `--profile {noisy,default,quiet}` Preset combining percentile and
  headroom. Defaults to `default`.
    * `noisy`: p95 with +5% warning / +10% critical headroom.
    * `default`: p99 with +10% warning / +20% critical headroom.
    * `quiet`: p99.9 with +20% warning / +50% critical headroom.
* `--percentile FLOAT` Override the profile's percentile (0 < P < 100).
* `--warning-headroom FLOAT` Override the profile's warning headroom
  (e.g. `0.10` for +10%).
* `--critical-headroom FLOAT` Override the profile's critical headroom.
* `--min-samples N` Skip rules whose metric returns fewer than N samples
  over the 7-day window. Default 100.
* `--max-delta N` Skip rules whose new threshold differs from the original
  by more than N× (either direction). Default 10.
* `--include GLOB` Tune only rules whose name matches this fnmatch glob.
  Repeatable.
* `--exclude GLOB` Skip rules whose name matches this glob. Repeatable.
  Overrides `--include`.
* `--rule NAME` Tune only this exact rule name. Repeatable.

#### Behavior:

The tool loads the input, strips each rule's trailing ` <operator> <value>`
suffix to isolate the bare metric, queries `/api/v1/query_range` over the
last 7 days (1-minute step), and computes a baseline percentile. For `>=`
and `>` operators, the upper percentile is used with positive headroom.
For `<=` and `<`, the lower percentile is used with negative headroom —
the "alert if it gets X% worse than last week" semantic applies to both
tails.

Rules that fail one of these checks are left unchanged in the output and
listed in the stdout summary and the audit report:

- **insufficient data**: fewer than `--min-samples` non-null samples
- **nonsensical**: new threshold would be ≤ 0
- **unreasonable delta**: new threshold differs from original by more than
  `--max-delta`× (guards against metric instability or algorithm error)
- **query failed**: metric endpoint returned an error
- **cannot parse expr**: the rule's expression didn't match the expected
  trailing-operator shape

#### Examples:

Tune with the default profile:

```shell
$ pipenv run python axonops.py --org $AXONOPS_ORG --cluster $AXONOPS_CLUSTER --token $AXONOPS_TOKEN \
    tune-alerts --input ./exported/alert_rules.json
```

Use the noisy preset to catch smaller deviations:

```shell
$ pipenv run python axonops.py --org $AXONOPS_ORG --cluster $AXONOPS_CLUSTER --token $AXONOPS_TOKEN \
    tune-alerts --input ./exported/alert_rules.json --profile noisy
```

Tune a subset of rules:

```shell
$ pipenv run python axonops.py --org $AXONOPS_ORG --cluster $AXONOPS_CLUSTER --token $AXONOPS_TOKEN \
    tune-alerts --input ./exported/alert_rules.json --include 'GC*' --exclude '*_paxos*'
```
```

### Step 6.2: Visual check

- [ ] Run:

```bash
tail -80 /opt/repos/axonops-ansible-collection/cli/README.md
```

Confirm the new section reads cleanly and code fences are balanced.

### Step 6.3: Commit

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection
git add cli/README.md
git status --short
git commit -m "$(cat <<'EOF'
docs(cli): document tune-alerts subcommand

Adds a README section covering the new tune-alerts subcommand:
flags, profile semantics, skip reasons, and three worked examples.
EOF
)"
```

---

## Task 7: `--from-api` follow-up (Commit 7 of 8)

**Goal:** Let the user skip `--input` and have the CLI GET `alert_rules.json` directly from the live API (using the same endpoint the `alerts` subcommand already calls). Writes the tuned file to a directory chosen by the user.

**Files:**

- Modify: `cli/axonopscli/components/tune_alerts.py`
- Modify: `cli/axonopscli/application.py`
- Modify: `cli/tests/test_tune_alerts_unittest.py`

### Step 7.1: Write failing tests

- [ ] Append to `cli/tests/test_tune_alerts_unittest.py`:

```python
class TestTuneAlertsFromApi(unittest.TestCase):

    def test_from_api_fetches_rules_endpoint_and_writes_output(self):
        from axonopscli.application import Application
        from axonopscli.axonops import AxonOps

        with tempfile.TemporaryDirectory() as tmp:
            # Canned: /api/v1/alert-rules returns _sample_input; /query_range returns samples
            alert_rules_body = _sample_input(cluster_name="bc1")
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
                    "--org", "acme", "--cluster", "bc1", "--token", "t",
                    "tune-alerts", "--from-api", "--output-dir", tmp,
                ])

            self.assertTrue(os.path.exists(os.path.join(tmp, "alert_rules.tuned.for.bc1.json")))

    def test_from_api_and_input_are_mutually_exclusive(self):
        from axonopscli.application import Application

        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(SystemExit):
                Application().run([
                    "--org", "acme", "--cluster", "bc1", "--token", "t",
                    "tune-alerts",
                    "--from-api", "--output-dir", tmp,
                    "--input", "/some/path.json",
                ])

    def test_neither_input_nor_from_api_errors(self):
        from axonopscli.application import Application

        with self.assertRaises(SystemExit):
            Application().run([
                "--org", "acme", "--cluster", "bc1", "--token", "t",
                "tune-alerts",
            ])
```

### Step 7.2: Run tests — verify fail

- [ ] Run:

```bash
python3 -m unittest tests.test_tune_alerts_unittest.TestTuneAlertsFromApi -v
```

Expected: FAIL (argparse error or SystemExit; `--from-api` doesn't exist yet).

### Step 7.3: Update `application.py` — make `--input` optional and add `--from-api` + `--output-dir`

- [ ] Find the `tune_alerts_parser.add_argument('--input', type=str, required=True, ...)` line and replace `required=True` with `required=False`:

```python
        tune_alerts_parser.add_argument('--input', type=str, required=False,
                                        help='Path to alert_rules.json (mutually exclusive with --from-api)')
```

- [ ] Add these two arguments immediately after the `--input` argument:

```python
        tune_alerts_parser.add_argument('--from-api', action='store_true', default=False,
                                        help='Fetch alert rules from the live API instead of --input')
        tune_alerts_parser.add_argument('--output-dir', type=str, default=None,
                                        help='Directory for output files (required with --from-api; defaults to the directory of --input)')
```

### Step 7.4: Update the validation block in `application.run` (the `if not getattr(parsed_result, ...)` section after `parser.parse_args`)

- [ ] Find the block near the end of `Application.run` that has other validation (e.g. `parser.error("--tables requires --keyspace")`) and add this validation immediately before `parsed_result.func(parsed_result)`:

```python
        # tune-alerts input source validation
        if getattr(parsed_result, 'func', None) == self.run_tune_alerts:
            has_input = bool(getattr(parsed_result, 'input', None))
            has_from_api = bool(getattr(parsed_result, 'from_api', False))
            if has_input and has_from_api:
                parser.error("--input and --from-api are mutually exclusive")
            if not has_input and not has_from_api:
                parser.error("tune-alerts requires either --input PATH or --from-api")
            if has_from_api and not getattr(parsed_result, 'output_dir', None):
                parser.error("--from-api requires --output-dir")
```

### Step 7.5: Add `fetch_from_api` method to `TuneAlertsOrchestrator`

- [ ] Append inside the `TuneAlertsOrchestrator` class in `cli/axonopscli/components/tune_alerts.py`:

```python
    ALERT_RULES_URL = "/api/v1/alert-rules/{org}/{cluster_type}/{cluster}"

    def fetch_from_api(self) -> dict:
        """Fetch alert_rules.json directly from the AxonOps API."""
        url = self.ALERT_RULES_URL.format(
            org=self.args.org,
            cluster_type=self.axonops.get_cluster_type(),
            cluster=self.args.cluster,
        )
        data = self.axonops.do_request(url=url, method="GET") or {}
        if "metricrules" not in data or not isinstance(data["metricrules"], list):
            raise ValueError("Fetched API response missing 'metricrules' list")
        return data
```

### Step 7.6: Update `run_tune_alerts` in `application.py` to use the new source logic

- [ ] Replace the body of `run_tune_alerts`:

```python
    def run_tune_alerts(self, args: argparse.Namespace):
        """ Run the alerts tuning """
        if args.v:
            print(f"Running alerts tuning on {args.org}/{args.cluster}")
            print(_scrubbed_args(args))

        axonops = self.get_axonops(args)

        from .components.tune_alerts import TuneAlertsOrchestrator

        config = self._build_tune_alerts_config(args)
        orchestrator = TuneAlertsOrchestrator(axonops, args, config)

        if args.from_api:
            import os as _os
            input_json = orchestrator.fetch_from_api()
            # write_output/report use the directory from a synthetic "input path"
            synthetic_input = _os.path.join(args.output_dir, "alert_rules.json")
            _os.makedirs(args.output_dir, exist_ok=True)
            source_label = synthetic_input
        else:
            input_json = orchestrator.load_input(args.input)
            source_label = args.input

        result = orchestrator.tune_all(input_json)
        json_path = orchestrator.write_output(source_label, result)
        orchestrator.write_audit_report(source_label, result)
        orchestrator.print_summary(result, json_path)
```

### Step 7.7: Run tests — verify pass

- [ ] Run:

```bash
python3 -m unittest tests.test_tune_alerts_unittest.TestTuneAlertsFromApi -v
```

Expected: 3 tests pass.

### Step 7.8: Run the full alerts test suite

- [ ] Run:

```bash
python3 -m unittest discover -s tests 2>&1 | tail -3
```

Expected: All new tests pass; pre-existing 3 `test_get_jwt` errors unchanged.

### Step 7.9: Update the README with the new flag

- [ ] Edit `cli/README.md`. In the `#### Options:` list for `tune-alerts`, add these two bullets between `--input` and `--profile`:

```markdown
* `--from-api` Fetch alert rules directly from the live API instead of
  reading from `--input`. Requires `--output-dir`. Mutually exclusive
  with `--input`.
* `--output-dir PATH` Directory for the tuned JSON and audit report when
  `--from-api` is used.
```

And update the `--input` bullet to clarify mutual exclusivity:

```markdown
* `--input` Path to the source `alert_rules.json`. Mutually exclusive
  with `--from-api`. The tuned output is written alongside it as
  `alert_rules.tuned.for.<cluster>.json` plus a `<...>.report.md`.
```

### Step 7.10: Commit

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection
git add cli/axonopscli/application.py cli/axonopscli/components/tune_alerts.py cli/tests/test_tune_alerts_unittest.py cli/README.md
git status --short
git commit -m "$(cat <<'EOF'
feat(cli): add --from-api flag to tune-alerts

Lets the user skip the separate alerts export step when iterating on
tuning. When --from-api is set, tune-alerts fetches alert_rules.json
directly from /api/v1/alert-rules/... (same endpoint the alerts
subcommand uses) and writes output into --output-dir.

--input and --from-api are mutually exclusive and argparse enforces
one-or-the-other.
EOF
)"
```

---

## Task 8: `--incident` follow-up (Commit 8 of 8)

**Goal:** Add `--incident YYYY-MM-DD` (repeatable) to exclude incident windows from baseline computation AND verify the tuned thresholds would have fired during incidents, auto-adjusting thresholds when the metric reflected the incident but the baseline-derived threshold would miss it.

**Files:**

- Modify: `cli/axonopscli/components/tune_alerts.py`
- Modify: `cli/axonopscli/application.py`
- Modify: `cli/tests/test_tune_alerts_unittest.py`
- Modify: `cli/README.md`

### Step 8.1: Write failing tests

- [ ] Append to `cli/tests/test_tune_alerts_unittest.py`:

```python
from datetime import datetime, timezone


def _day_range(date_str):
    """Return (start_ts, end_ts) for the given YYYY-MM-DD UTC day."""
    day = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    start = int(day.timestamp())
    end = start + 24 * 60 * 60 - 1
    return (start, end)


class TestIncidentFlag(unittest.TestCase):

    def _run_with_incident(self, tmp, input_json, baseline_samples, incident_samples, incident_date="2026-04-10"):
        """Helper: patches MetricQuerier so baseline query (excluding incident)
        returns baseline_samples and incident-window query returns incident_samples.
        The orchestrator differentiates calls by the start timestamp."""
        from axonopscli.application import Application
        from axonopscli.axonops import AxonOps

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

        prom_placeholder = {"status": "success", "data": {"resultType": "matrix", "result": []}}

        with patch('axonopscli.components.tune_alerts.MetricQuerier.query', new=fake_query):
            Application().run([
                "--org", "acme", "--cluster", "bc1", "--token", "t",
                "tune-alerts", "--input", input_path,
                "--incident", incident_date,
            ])

        with open(os.path.join(tmp, "alert_rules.tuned.for.bc1.json")) as f:
            tuned = json.load(f)
        with open(os.path.join(tmp, "alert_rules.tuned.for.bc1.report.md")) as f:
            report = f.read()
        return tuned, report

    def test_incident_day_verified_no_adjustment_needed(self):
        # Baseline p99 ≈ 99 → critical = 99 * 1.20 = 118.8
        # Incident peak = 500 → incident >> critical → "Yes (baseline)"
        with tempfile.TemporaryDirectory() as tmp:
            tuned, report = self._run_with_incident(
                tmp,
                _sample_input(cluster_name="bc1"),
                baseline_samples=list(range(100)),   # p99 ≈ 99
                incident_samples=[500, 600, 700],    # peak 700, way above 118.8
            )
            self.assertIn("Incident coverage (2026-04-10)", report)
            self.assertIn("Yes (baseline)", report)
            # No adjustment → critical stays at baseline-derived value
            rule = tuned["metricrules"][0]
            self.assertLess(rule["criticalValue"], 200)

    def test_incident_adjusts_threshold_when_baseline_would_miss(self):
        # Baseline p99 ≈ 990 → critical = 990 * 1.20 = 1188
        # Incident peak = 800 → baseline CRITICAL wouldn't fire (800 < 1188)
        # But is the metric impacted? p99 of baseline = 990. Is 800 outside baseline normal?
        # Per Case C definition: NOT IMPACTED if incident_peak <= p99(baseline).
        # Here 800 <= 990 → metric NOT impacted → no adjustment
        with tempfile.TemporaryDirectory() as tmp:
            tuned, report = self._run_with_incident(
                tmp,
                _sample_input(cluster_name="bc1"),
                baseline_samples=list(range(1000)),  # p99 = 990
                incident_samples=[500, 700, 800],    # peak 800 < 990 (baseline p99)
            )
            self.assertIn("metric not impacted by incident", report)

    def test_incident_metric_impacted_triggers_adjustment(self):
        # Baseline p99 = 99 → critical = 99 * 1.20 = 118.8
        # Incident peak = 150 → 150 > p99 baseline (99) → metric impacted
        # But: would critical fire? 150 >= 118.8 → YES, no adjustment needed
        # So construct one where threshold still misses after headroom:
        # Baseline: [1..100] (p99 ≈ 99), critical = 99 * 1.20 = 118.8
        # Incident: peak = 100 → NOT impacted (100 <= 99 is false, but 100 > 99, so IMPACTED).
        # Would baseline critical (118.8) fire on 100? No, 100 < 118.8. So we adjust.
        # Adjusted critical = min(118.8, 100 * 0.95) = 95
        with tempfile.TemporaryDirectory() as tmp:
            tuned, report = self._run_with_incident(
                tmp,
                _sample_input(cluster_name="bc1"),
                baseline_samples=list(range(1, 101)),   # p99 ≈ 99.01
                incident_samples=[50, 80, 100],          # peak 100 > 99 (impacted), but < 118.8 (would miss)
            )
            self.assertIn("Yes (adjusted)", report)
            rule = tuned["metricrules"][0]
            # Adjusted critical = 100 * 0.95 = 95
            self.assertLessEqual(rule["criticalValue"], 100)

    def test_multiple_incidents(self):
        # Both incident dates should appear in report
        # Using tempfile + inline patch because we need to pass two --incident flags
        from axonopscli.application import Application
        from axonopscli.axonops import AxonOps

        with tempfile.TemporaryDirectory() as tmp:
            input_path = os.path.join(tmp, "alert_rules.json")
            with open(input_path, "w") as f:
                json.dump(_sample_input(cluster_name="bc1"), f)

            def fake_query(self, promql, start, end, step="1m"):
                return list(range(1000))

            with patch('axonopscli.components.tune_alerts.MetricQuerier.query', new=fake_query):
                Application().run([
                    "--org", "acme", "--cluster", "bc1", "--token", "t",
                    "tune-alerts", "--input", input_path,
                    "--incident", "2026-04-10", "--incident", "2026-04-11",
                ])

            with open(os.path.join(tmp, "alert_rules.tuned.for.bc1.report.md")) as f:
                report = f.read()
            self.assertIn("Incident coverage (2026-04-10)", report)
            self.assertIn("Incident coverage (2026-04-11)", report)
```

### Step 8.2: Run tests — verify fail

- [ ] Run:

```bash
python3 -m unittest tests.test_tune_alerts_unittest.TestIncidentFlag -v
```

Expected: FAIL — `--incident` flag doesn't exist yet.

### Step 8.3: Add `--incident` to argparse and thread through config

- [ ] In `application.py`, add to the tune-alerts subparser (inside the block from Task 5.3):

```python
        tune_alerts_parser.add_argument('--incident', action='append', default=[],
                                        help='YYYY-MM-DD UTC day to exclude from baseline and verify coverage for (repeatable)')
```

- [ ] In `_build_tune_alerts_config`, thread `incidents` into the config constructor (add a new field to the dataclass in Step 8.4):

```python
        return TuneAlertsConfig(
            profile=args.profile,
            percentile=args.percentile if args.percentile is not None else p_percentile,
            warning_headroom=args.warning_headroom if args.warning_headroom is not None else p_warn,
            critical_headroom=args.critical_headroom if args.critical_headroom is not None else p_crit,
            min_samples=args.min_samples,
            max_delta=args.max_delta,
            include=list(args.include or []),
            exclude=list(args.exclude or []),
            rules=list(args.rule or []),
            incidents=list(args.incident or []),
        )
```

### Step 8.4: Add `incidents` to `TuneAlertsConfig` and incident logic to orchestrator

- [ ] Update `TuneAlertsConfig` in `cli/axonopscli/components/tune_alerts.py`:

```python
@dataclass
class TuneAlertsConfig:
    profile: str
    percentile: float
    warning_headroom: float
    critical_headroom: float
    min_samples: int
    max_delta: float
    include: list
    exclude: list
    rules: list
    incidents: list = None          # list[str] of YYYY-MM-DD

    def __post_init__(self):
        if self.incidents is None:
            self.incidents = []
```

- [ ] Add a helper for resolving incident window ranges. Append at module level:

```python
from datetime import datetime, timezone, timedelta


def _incident_day_range(date_str: str) -> tuple:
    """Return (start_ts, end_ts_inclusive) in Unix seconds for a YYYY-MM-DD UTC day."""
    day = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    start = int(day.timestamp())
    end = start + 24 * 60 * 60 - 1
    return (start, end)
```

- [ ] Extend `RuleOutcome` with incident-related fields:

```python
@dataclass
class RuleOutcome:
    rule_name: str
    status: str
    reason: Optional[str] = None
    old_warning: Optional[float] = None
    old_critical: Optional[float] = None
    new_warning: Optional[float] = None
    new_critical: Optional[float] = None
    percentile_value: Optional[float] = None
    sample_count: Optional[int] = None
    operator: Optional[str] = None
    incident_coverage: Optional[list] = None   # list[dict] per incident
```

- [ ] Rewrite `_tune_one` to handle incidents. Replace the whole method body with:

```python
    def _tune_one(self, rule: dict, start_ts: int, end_ts: int) -> RuleOutcome:
        from axonopscli.utils import HTTPCodeError

        name = rule.get("alert", "<unnamed>")
        expr = rule.get("expr", "")
        old_warning = rule.get("warningValue")
        old_critical = rule.get("criticalValue")

        if not self.filter.accepts(name):
            return RuleOutcome(
                rule_name=name, status="filtered", reason="excluded by filter",
                old_warning=old_warning, old_critical=old_critical,
            )

        try:
            bare, operator, _old_str = ExprRewriter.strip_threshold(expr)
        except ValueError as e:
            return RuleOutcome(
                rule_name=name, status="skipped", reason=f"cannot parse expr: {e}",
                old_warning=old_warning, old_critical=old_critical,
            )

        # Build the list of incident windows
        incident_windows = [_incident_day_range(d) for d in self.config.incidents]

        querier = MetricQuerier(self.axonops, self.args)

        # Baseline: either a single 7-day query (no incidents) or multiple
        # sub-range queries skipping over each incident window.
        try:
            if incident_windows:
                baseline_samples = self._baseline_samples_excluding(
                    querier, bare, start_ts, end_ts, incident_windows,
                )
            else:
                baseline_samples = querier.query(bare, start=start_ts, end=end_ts, step="1m")
        except HTTPCodeError as e:
            return RuleOutcome(
                rule_name=name, status="skipped", reason=f"query failed: {e}",
                old_warning=old_warning, old_critical=old_critical, operator=operator,
            )

        if len(baseline_samples) < self.config.min_samples:
            return RuleOutcome(
                rule_name=name, status="skipped",
                reason=f"insufficient data ({len(baseline_samples)} samples)",
                old_warning=old_warning, old_critical=old_critical,
                operator=operator, sample_count=len(baseline_samples),
            )

        try:
            calc = ThresholdCalculator.compute(
                samples=baseline_samples,
                operator=operator,
                percentile=self.config.percentile,
                warning_headroom=self.config.warning_headroom,
                critical_headroom=self.config.critical_headroom,
            )
        except ValueError as e:
            return RuleOutcome(
                rule_name=name, status="skipped", reason=f"threshold compute error: {e}",
                old_warning=old_warning, old_critical=old_critical, operator=operator,
            )

        new_warning = calc.new_warning
        new_critical = calc.new_critical
        incident_coverage = []

        # Incident coverage: for each incident, check whether the baseline-derived
        # threshold would fire, and adjust downward (for >=/>) or upward (for <=/<)
        # if the metric reflected the incident but threshold would miss.
        for window in incident_windows:
            inc_start, inc_end = window
            try:
                incident_samples = querier.query(bare, start=inc_start, end=inc_end, step="1m")
            except HTTPCodeError as e:
                incident_coverage.append({
                    "date": datetime.fromtimestamp(inc_start, tz=timezone.utc).strftime("%Y-%m-%d"),
                    "status": "query failed",
                    "peak": None,
                    "action": f"query failed: {e}",
                })
                continue

            if not incident_samples:
                incident_coverage.append({
                    "date": datetime.fromtimestamp(inc_start, tz=timezone.utc).strftime("%Y-%m-%d"),
                    "status": "no data",
                    "peak": None,
                    "action": "no samples during incident window",
                })
                continue

            if operator in (">=", ">"):
                incident_peak = max(incident_samples)
                would_fire = incident_peak >= new_critical
                metric_impacted = incident_peak > calc.percentile_value
            else:  # <=, <
                incident_peak = min(incident_samples)
                would_fire = incident_peak <= new_critical
                metric_impacted = incident_peak < calc.percentile_value

            entry = {
                "date": datetime.fromtimestamp(inc_start, tz=timezone.utc).strftime("%Y-%m-%d"),
                "peak": incident_peak,
            }

            if would_fire:
                entry["status"] = "Yes (baseline)"
                entry["action"] = "none"
            elif not metric_impacted:
                entry["status"] = "N/A"
                entry["action"] = "metric not impacted by incident"
            else:
                # Adjust
                if operator in (">=", ">"):
                    adjusted_critical = min(new_critical, incident_peak * 0.95)
                    adjusted_warning = min(new_warning, incident_peak * 0.95 * (new_warning / new_critical) if new_critical else incident_peak * 0.95)
                else:
                    adjusted_critical = max(new_critical, incident_peak * 1.05)
                    adjusted_warning = max(new_warning, incident_peak * 1.05 * (new_warning / new_critical) if new_critical else incident_peak * 1.05)
                new_warning = adjusted_warning
                new_critical = adjusted_critical
                entry["status"] = "Yes (adjusted)"
                entry["action"] = f"critical {_format_value(calc.new_critical)} → {_format_value(adjusted_critical)}"

            incident_coverage.append(entry)

        # Sanity clamps
        if new_warning <= 0 or new_critical <= 0:
            return RuleOutcome(
                rule_name=name, status="skipped",
                reason=f"nonsensical (new warning={new_warning}, critical={new_critical})",
                old_warning=old_warning, old_critical=old_critical, operator=operator,
                sample_count=calc.sample_count, incident_coverage=incident_coverage,
            )

        if self._unreasonable_delta(old_warning, new_warning) or \
           self._unreasonable_delta(old_critical, new_critical):
            return RuleOutcome(
                rule_name=name, status="skipped",
                reason=f"unreasonable delta (max_delta={self.config.max_delta})",
                old_warning=old_warning, old_critical=old_critical,
                new_warning=new_warning, new_critical=new_critical,
                operator=operator, sample_count=calc.sample_count,
                percentile_value=calc.percentile_value,
                incident_coverage=incident_coverage,
            )

        rule["warningValue"] = _round_threshold(new_warning)
        rule["criticalValue"] = _round_threshold(new_critical)
        rule["expr"] = ExprRewriter.rewrite(expr, new_warning=rule["warningValue"])

        return RuleOutcome(
            rule_name=name, status="tuned",
            old_warning=old_warning, old_critical=old_critical,
            new_warning=rule["warningValue"], new_critical=rule["criticalValue"],
            operator=operator, sample_count=calc.sample_count,
            percentile_value=calc.percentile_value,
            incident_coverage=incident_coverage,
        )

    def _baseline_samples_excluding(self, querier, promql, start_ts, end_ts, incident_windows):
        """Query the 7-day window minus incident-day windows as separate sub-queries."""
        # Sort and merge incident windows
        sorted_windows = sorted(incident_windows)
        cursor = start_ts
        baseline = []
        for inc_start, inc_end in sorted_windows:
            if inc_end < start_ts or inc_start > end_ts:
                continue  # incident entirely outside the 7-day window
            clipped_start = max(inc_start, start_ts)
            clipped_end = min(inc_end, end_ts)
            if cursor < clipped_start:
                baseline.extend(querier.query(promql, start=cursor, end=clipped_start - 1, step="1m"))
            cursor = max(cursor, clipped_end + 1)
        if cursor <= end_ts:
            baseline.extend(querier.query(promql, start=cursor, end=end_ts, step="1m"))
        return baseline
```

### Step 8.5: Extend `_render_audit_report` to emit "Incident coverage" sections

- [ ] In `TuneAlertsOrchestrator._render_audit_report`, append before the return statement:

```python
        # Incident coverage sections (one per incident date)
        if self.config.incidents:
            for incident_date in sorted(self.config.incidents):
                # Collect per-rule entries for this incident
                rows = []
                for o in result.outcomes:
                    if not o.incident_coverage:
                        continue
                    for entry in o.incident_coverage:
                        if entry.get("date") == incident_date:
                            rows.append((o.rule_name, entry))
                if not rows:
                    continue
                lines.extend([
                    f"## Incident coverage ({incident_date})",
                    "",
                    "| Rule | Would have fired? | Incident peak | Action |",
                    "|---|---|---|---|",
                ])
                for rule_name, entry in rows:
                    lines.append(
                        f"| {rule_name} | {entry['status']} | "
                        f"{_format_value(entry.get('peak'))} | {entry['action']} |"
                    )
                lines.append("")
```

### Step 8.6: Run incident tests — verify pass

- [ ] Run:

```bash
python3 -m unittest tests.test_tune_alerts_unittest.TestIncidentFlag -v
```

Expected: 4 tests pass.

### Step 8.7: Run full module and full test suite

- [ ] Run:

```bash
python3 -m unittest tests.test_tune_alerts_unittest 2>&1 | tail -3
python3 -m unittest discover -s tests 2>&1 | tail -3
```

Expected: All tune-alerts tests pass; overall suite reports 3 pre-existing `test_get_jwt` errors unchanged.

### Step 8.8: Update README with `--incident`

- [ ] In `cli/README.md`, in the `tune-alerts` Options section, add this bullet at the end:

```markdown
* `--incident YYYY-MM-DD` UTC day to exclude from the baseline and verify
  coverage for. When set, the tuned threshold is verified against the
  incident peak: if the metric reflected the incident but the baseline-
  derived threshold wouldn't have fired, the threshold is automatically
  adjusted so it would. The audit report gains a "Incident coverage"
  section per incident. Repeatable.
```

### Step 8.9: Commit

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection
git add cli/axonopscli/application.py cli/axonopscli/components/tune_alerts.py cli/tests/test_tune_alerts_unittest.py cli/README.md
git status --short
git commit -m "$(cat <<'EOF'
feat(cli): add --incident flag to tune-alerts

Repeatable --incident YYYY-MM-DD flag excludes the named UTC days
from baseline percentile computation and verifies that the tuned
thresholds would have fired on each incident day.

If the baseline-derived threshold wouldn't have fired AND the metric
reflected the incident (incident peak exceeds the baseline
percentile), automatically adjusts the threshold so it would have
fired (5% safety margin). If the metric didn't reflect the incident
(peak within baseline normal range), leaves the threshold unchanged
and notes "metric not impacted by incident" in the audit report.

Audit report gains a "Incident coverage" section per incident with
per-rule status, peak value, and action taken.

V1 uses simple max/min comparison, not `for`-duration-aware sustained
violation. Acknowledged trade-off; over-estimates detection capability
vs. real AxonOps which requires sustained violation. Good enough for
"did we miss an event we should have caught"; upgradable later.
EOF
)"
```

---

## Final verification

### Step F.1: Full test suite

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection/cli
python3 -m unittest discover -s tests 2>&1 | tail -5
```

Expected: ~95 tests run; 3 pre-existing `test_get_jwt` errors unchanged; all new tests pass.

### Step F.2: Commit history check

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection
git log --oneline main..HEAD
```

Expected: 11 alerts-export commits + 9 tune-alerts commits (1 spec + 8 impl), in this order (newest at top):

```
<sha> feat(cli): add --incident flag to tune-alerts
<sha> feat(cli): add --from-api flag to tune-alerts
<sha> docs(cli): document tune-alerts subcommand
<sha> feat(cli): wire tune-alerts CLI subcommand
<sha> feat(cli): add TuneAlertsOrchestrator
<sha> feat(cli): add MetricQuerier for /api/v1/query_range
<sha> feat(cli): add ExprRewriter for alert tuning
<sha> feat(cli): add ThresholdCalculator for alert tuning
4ca6282 docs(plans): design for tune-alerts CLI subcommand
<… alerts-export-cli commits …>
```

### Step F.3: Smoke-test the CLI end-to-end (no live API)

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection/cli
python3 -c "from axonopscli.application import Application; Application().run(['tune-alerts', '--help'])"
```

Expected: argparse help lists all flags: `--input`, `--from-api`, `--output-dir`, `--profile`, `--percentile`, `--warning-headroom`, `--critical-headroom`, `--min-samples`, `--max-delta`, `--include`, `--exclude`, `--rule`, `--incident`.

### Step F.4: Diff review

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection
git diff main..HEAD --stat
```

Expected: ~8–10 files changed, ~2500 insertions including the spec + plan + implementation + tests. The new file `cli/axonopscli/components/tune_alerts.py` should be ~500–700 lines.

### Step F.5: Hand control back

- [ ] Hand control back to the engineering manager (the calling agent). Do NOT run `/review`, `/code-review:code-review`, `/pr-review-toolkit:review-pr`, `/code-simplifier`, or `/security-review` — those are the manager's responsibility per PROMPT.ORG.

---

## Notes for the implementing engineer

- **DRY:** Many helpers from the existing alerts export feature are reusable. Notably `_scrubbed_args` for verbose printing; the `HTTPCodeError` from `axonopscli.utils`; the atomic file-creation pattern from `AlertsExporter._write_resource` (though `tune_alerts` writes larger files via a slightly simpler flow). Do not duplicate the redactor — tune-alerts does not write secrets.
- **YAGNI:** Explicitly out-of-scope features from the spec: `for`-duration tuning, per-filter per-rule queries, log/event rules, in-place modification of input, pushing back to the server, historical run comparison, time-range incident windows. Resist scope creep.
- **TDD:** Every implementation step has its test written and failing first. Do not implement without seeing the failure.
- **Pre-existing test failures (`do_login`, `get_jwt`):** Out of scope. Do not touch.
- **Branch:** Stay on `alerts-export-cli`. Do NOT create a new branch.
- **Signing:** `commit.gpgsign` is `false` for this repo (set by the user earlier). Do not touch that config.
- **One commit per task:** Do not squash. Do not amend prior commits.
- **If a step fails unexpectedly:** Stop. Report back to the calling agent with full context. Do not invent fixes.
- **URL verification (Task 3.6):** If the empirical smoke test can't be run (no credentials), proceed without it. The unit tests lock in the URL template shape; if the live server disagrees, the test in `TestApplicationRunTuneAlerts.test_application_run_tune_alerts_end_to_end` still passes (it mocks `AxonOps.do_request`), but the first real user invocation will 404. Flag this explicitly in the review notes so the manager can exercise with live credentials before merge.
