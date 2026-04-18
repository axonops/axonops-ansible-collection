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
