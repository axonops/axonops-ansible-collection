import fnmatch
import json
import math
import os
import re
import sys
import time
import urllib.parse
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from axonopscli.api import (
    ALERT_RULES_URL, EVENTS_SEARCH_URL, METRIC_LABEL_VALUES_URL, QUERY_RANGE_URL,
)


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


# Pattern mirrors the stripping regex used by the existing Ansible
# alert_rule.py module (line ~253): expressions always end with
# ` <operator> <value>`.
_TRAILING_THRESHOLD_RE = re.compile(r'^(.*)\s(<=|>=|<|>|==|!=)\s(\S+)$')

# Matches a metric selector `name{<labels>}`. The label body cannot contain
# braces (PromQL selectors don't nest), so `[^{}]*` is safe even when label
# values carry commas. The metric name precedes the brace; function calls use
# `(` and the `by (...)` grouping clause uses parens, so neither is matched.
_METRIC_SELECTOR_RE = re.compile(r"([a-zA-Z_:][a-zA-Z0-9_:]*)\s*\{([^{}]*)\}")

# A single label matcher inside a selector body: `label OP 'value'`. The value
# is single-quoted and may itself contain commas, so matching whole matchers
# (rather than splitting the body on commas) keeps comma-bearing values intact.
_LABEL_MATCHER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\s*(?:=~|!~|!=|=)\s*'[^']*'")
# An exact-equality matcher against an empty value, e.g. `host_id=''` or
# `host_id=~''`. Negated forms (`!=''`, `!~''`) mean "non-empty" and are kept.
_EMPTY_EQ_MATCHER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\s*=~?\s*''$")

# A rule whose leading metric selector is `events{...}`. AxonOps stores log
# alerts under this metric (via log_alert_rule) without a PromQL trailing
# threshold, and the event-type alerts (Failed Auth / DDL / DML / JMX) keep
# 500ing on query_range. Either way the tuner can't usefully threshold-tune
# them, so we skip them up front with one short reason.
_EVENTS_METRIC_RE = re.compile(r"^\s*events\s*\{")


def _is_event_metric_rule(expr) -> bool:
    """True if the rule's expr is an `events{...}` selector (log alert or
    event-type metric alert) — see _EVENTS_METRIC_RE."""
    if not expr:
        return False
    return bool(_EVENTS_METRIC_RE.match(expr))


def parse_set_label_arg(arg: str) -> tuple:
    """Parse a ``--set-label`` value of the form ``[METRIC_GLOB:]LABEL=VALUE``.

    Returns ``(metric_glob_or_None, label, value)``. ``LABEL`` must be a valid
    Prometheus label name (no colon), which lets us split the optional metric
    glob on the last ``:`` unambiguously even when the glob itself contains a
    colon (recording-rule style names). Raises ValueError on malformed input.
    """
    left, sep, value = arg.partition("=")
    if not sep:
        raise ValueError(f"--set-label must be LABEL=VALUE or METRIC_GLOB:LABEL=VALUE: {arg!r}")
    left = left.strip()
    value = value.strip()
    if ":" in left:
        metric_glob, _, label = left.rpartition(":")
        metric_glob = metric_glob.strip() or None
        label = label.strip()
    else:
        metric_glob, label = None, left
    if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", label):
        raise ValueError(f"invalid label name in --set-label: {label!r}")
    if value == "" or "'" in value:
        raise ValueError(f"invalid value in --set-label (empty or contains quote): {value!r}")
    return (metric_glob, label, value)


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

    @staticmethod
    def set_label(expr: str, label: str, value: str, metric_glob: str = None) -> str:
        """Pin a label selector to a single exact-match value.

        For every metric selector ``name{...}`` in ``expr`` whose name matches
        ``metric_glob`` (fnmatch glob; ``None`` matches all) and that already
        contains a matcher for ``label``, replace that matcher with
        ``label='value'`` (exact equality, regardless of the original
        ``=``/``=~``/``!=``/``!~`` operator and value). Selectors lacking the
        label are left untouched — this pins existing labels, it never injects
        a new one.

        Used to retarget broken multi-value selectors (e.g. the comma-joined
        ``keyspace=~'a,b,c'`` lists that match no series) onto a single active
        keyspace/table so the tuner queries representative workload data. The
        ``metric_glob`` lets callers confine an overloaded label like ``scope``
        (a table name on ``cas_Table_*`` metrics, a request type or thread pool
        elsewhere) to just the metrics where it means a table.
        """
        label_re = re.compile(
            r"(?<![A-Za-z0-9_])" + re.escape(label) + r"\s*(?:=~|!~|=|!=)\s*'[^']*'"
        )
        replacement = f"{label}='{value}'"

        def _rewrite_selector(m):
            metric_name, body = m.group(1), m.group(2)
            if metric_glob is not None and not fnmatch.fnmatchcase(metric_name, metric_glob):
                return m.group(0)
            return f"{metric_name}{{{label_re.sub(replacement, body)}}}"

        return _METRIC_SELECTOR_RE.sub(_rewrite_selector, expr)

    @staticmethod
    def drop_empty_matchers(expr: str) -> str:
        """Remove exact-equality matchers against an empty value (``label=''``
        / ``label=~''``) from every metric selector.

        AxonOps seeds some default rules with placeholder matchers like
        ``events{host_id='',...}``. The alert engine treats an empty host_id as
        "all hosts", but the raw query_range endpoint returns 500 for an
        empty-string matcher. Stripping these from the *query* expression lets
        the sample query succeed (aggregating across hosts); the stored rule
        expr — written back and applied to the cluster — is left untouched.

        Negated empty matchers (``label!=''``) mean "non-empty" and are kept.
        """
        def _rewrite_selector(m):
            metric_name, body = m.group(1), m.group(2)
            kept = [
                matcher for matcher in _LABEL_MATCHER_RE.findall(body)
                if not _EMPTY_EQ_MATCHER_RE.match(matcher.strip())
            ]
            return f"{metric_name}{{{','.join(kept)}}}"

        return _METRIC_SELECTOR_RE.sub(_rewrite_selector, expr)


def _format_value(v) -> str:
    """Format a numeric threshold without a trailing `.0` when it's whole."""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


def _md_cell(s) -> str:
    """Escape a value for use inside a markdown table cell."""
    if s is None:
        return ""
    return str(s).replace("|", "\\|").replace("\n", " ")


def _looks_like_percentage(bare_metric: str, old_warning, old_critical) -> bool:
    """Heuristic: does this expression define a metric that can't exceed 100?

    Two signals count as "this is a percentage":
      1. The bare metric ends with `* 100` (Prometheus idiom for converting
         a 0..1 ratio to a percent, e.g. `avg(disk_used/disk_total) * 100`).
      2. The bare metric contains `percent` (case-insensitive) or a literal
         `%` — catches metric names like `host_Disk_UsedPercent` or
         `cpu_percent_busy` that report a value already in 0..100.

    Either signal triggers the clamp. Both original thresholds must be in
    the 0..100 range as a sanity guard — protects against false positives
    on expressions like `foo * 100 >= 500` where the `* 100` is a unit
    conversion rather than a percentage conversion.
    """
    bare_l = bare_metric.lower()
    has_percent_signal = (
        bare_metric.rstrip().endswith("* 100")
        or "percent" in bare_l
        or "%" in bare_metric
    )
    if not has_percent_signal:
        return False
    for v in (old_warning, old_critical):
        try:
            if v is None or not (0 <= float(v) <= 100):
                return False
        except (TypeError, ValueError):
            return False
    return True


class MetricQuerier:
    """Query /api/v1/query_range and return a flat list of numeric samples."""

    def __init__(self, axonops, args):
        self.axonops = axonops
        self.args = args

    def query(self, promql: str, start: int, end: int, step: str = "1m") -> list:
        """Return a flat list of non-null, finite, float samples across all series.

        start/end are Unix epoch seconds. step is a Prometheus duration string
        (e.g. '1m', '15s'). Raises HTTPCodeError on transport/server failure.
        """
        qs = urllib.parse.urlencode({
            "query": promql,
            "start": start,
            "end": end,
            "step": step,
        })
        url = f"{QUERY_RANGE_URL}?{qs}"
        response = self.axonops.do_request(url=url, method="GET")
        return self._flatten(response)

    @staticmethod
    def _flatten(response) -> list:
        if not isinstance(response, dict):
            return []
        data = response.get("data")
        if not isinstance(data, dict):
            return []
        result = data.get("result")
        if not isinstance(result, list):
            return []
        out = []
        for series in result:
            if not isinstance(series, dict):
                continue
            values = series.get("values")
            if not isinstance(values, list):
                continue
            for point in values:
                # point is expected to be [timestamp, value_string_or_null]
                if not isinstance(point, (list, tuple)) or len(point) != 2:
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


class SchemaDiagnostic:
    """Probe the cluster's actual metric label values to explain a 0-series
    query result.

    When a tuning query returns 0 samples, the cause is almost always one
    of two things: (a) the rule is correct but the metric is genuinely 0
    on the cluster ("any > 0 is bad" rules — pin in policy), or (b) the
    rule's expr filters on a label name the cluster doesn't emit (broken
    schema — fix the expr). Distinguishing the two used to require manual
    `curl` probing of /metricLabelValues; this class automates it.

    For each positive equality matcher in the expr's first metric selector
    (``label='value'`` or ``label=~'pattern'``), queries the cluster for
    the distinct values of that label on that metric. If the API returns
    no values for a label, that label is the schema break — report it.

    Probe results are memoised per ``(metric, label)`` for the lifetime of
    the diagnostic instance.
    """

    # Single-label matchers in the positive-equality form. The negated
    # forms (!=, !~) don't carry information about which values exist, so
    # don't probe them.
    _POSITIVE_MATCHER_RE = re.compile(
        r"([A-Za-z_][A-Za-z0-9_]*)\s*=~?\s*'([^']*)'"
    )

    def __init__(self, axonops, args):
        self.axonops = axonops
        self.args = args
        self._cache = {}  # (metric, label) -> list[str]

    def _label_values(self, metric: str, label: str):
        key = (metric, label)
        if key in self._cache:
            return self._cache[key]
        cluster_type = getattr(self.axonops, "get_cluster_type", lambda: None)() or "cassandra"
        path = METRIC_LABEL_VALUES_URL.format(
            org=self.args.org,
            cluster_type=cluster_type,
            cluster=self.args.cluster,
        )
        qs = urllib.parse.urlencode({
            "query": metric,
            "regex": f"{label}=([^:]+)",
        })
        try:
            resp = self.axonops.do_request(url=f"{path}?{qs}", method="GET")
        except Exception:
            # Probe failures are diagnostic-only; don't escalate. Cache the
            # miss so we don't hammer the API on a broken endpoint.
            self._cache[key] = None
            return None
        if not isinstance(resp, dict):
            self._cache[key] = None
            return None
        data = resp.get("data")
        if not isinstance(data, list):
            self._cache[key] = None
            return None
        self._cache[key] = data
        return data

    def diagnose(self, expr: str):
        """Return a short ``broken_schema: …`` string explaining why a
        0-series query failed, or ``None`` if no schema break was found
        (i.e. all labels in the expr have values on the cluster, so the
        metric is genuinely 0).
        """
        m = _METRIC_SELECTOR_RE.search(expr)
        if not m:
            return None
        metric = m.group(1)
        body = m.group(2)
        for label, _value in self._POSITIVE_MATCHER_RE.findall(body):
            # Skip well-known PromQL-internal labels — they're tested
            # against on shipped rules but cluster won't list them via
            # metricLabelValues.
            if label in ("__name__",):
                continue
            values = self._label_values(metric, label)
            if values is None:
                # Probe failed; can't diagnose. Stop trying so we don't
                # accumulate misleading "0 values" reports.
                return None
            if not values:
                return (
                    f"broken_schema: label {label!r} has 0 values on metric "
                    f"{metric!r}; rewrite the expr to use a label the cluster "
                    f"actually emits"
                )
        return None


class EventsQuerier:
    """Count log/event records matching an `events{...}` rule's selector
    over a time window.

    The metrics ``query_range`` endpoint returns HTTP 500 for ``events{...}``
    queries — events live in a separate log/event store, not the metrics
    TSDB. This class hits the dedicated POST ``/events`` search endpoint
    and reads ``metadata._count`` so the tuner can derive thresholds for
    event-shape rules instead of skipping them all up front.
    """

    # Matches every positive (=) and quoted-equality matcher in an events
    # selector body. The events store uses substring matches for `message`
    # (e.g. ``message="+word +word"``), so we copy the matcher value
    # verbatim into the request body — no further parsing.
    _MATCHER_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*)\s*=\s*"([^"]*)"')
    _MATCHER_RE_SINGLE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*'([^']*)'")

    def __init__(self, axonops, args):
        self.axonops = axonops
        self.args = args

    @classmethod
    def parse_filters(cls, expr: str) -> dict:
        """Pull source / level / message / type / host_id out of an events
        selector body. Returns an empty dict if the expr isn't recognised
        as ``events{...}``."""
        m = re.search(r"events\s*\{([^}]*)\}", expr)
        if not m:
            return {}
        body = m.group(1)
        out = {}
        for lr in (cls._MATCHER_RE, cls._MATCHER_RE_SINGLE):
            for label, value in lr.findall(body):
                out[label] = value
        return out

    def count(self, filters: dict, start: int, end: int):
        """Return the total event count matching ``filters`` between
        ``start`` and ``end`` (epoch seconds), or None if the endpoint
        wasn't usable. Empty / missing filter keys are sent as empty
        strings — the events backend treats them as wildcards."""
        from axonopscli.utils import HTTPCodeError

        cluster_type = getattr(self.axonops, "get_cluster_type", lambda: None)() or "cassandra"
        path = EVENTS_SEARCH_URL.format(
            org=self.args.org,
            cluster_type=cluster_type,
            cluster=self.args.cluster,
        )
        qs = urllib.parse.urlencode({"start": start, "end": end, "limit": 1})
        body = {
            "source":  filters.get("source", ""),
            "level":   filters.get("level", ""),
            "message": filters.get("message", ""),
            "host_id": filters.get("host_id", "") or "",
            "type":    filters.get("type", ""),
            "f1": "",
            "f2": "",
            "search_after": None,
        }
        try:
            resp = self.axonops.do_request(
                url=f"{path}?{qs}", method="POST", json_data=body,
            )
        except HTTPCodeError:
            return None
        except Exception:
            return None
        if not isinstance(resp, dict):
            return None
        meta = resp.get("metadata")
        if not isinstance(meta, dict):
            return None
        try:
            return int(meta.get("_count", 0))
        except (TypeError, ValueError):
            return None


# Map ``for: "5m"`` / ``"30s"`` / ``"2h"`` / ``"500ms"`` to minutes (float).
# Default to 5m when missing/empty — that's the platform default.
def _for_to_minutes(for_str) -> float:
    if not for_str:
        return 5.0
    m = re.match(r"^\s*(\d+)\s*(ms|s|m|h)?\s*$", str(for_str))
    if not m:
        return 5.0
    n = int(m.group(1))
    unit = m.group(2) or "m"
    return {"ms": n / 60000.0, "s": n / 60.0, "m": float(n), "h": n * 60.0}[unit]


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


def _incident_day_range(date_str: str) -> tuple:
    """Return (start_ts, end_ts_inclusive) in Unix seconds for a YYYY-MM-DD UTC day."""
    day = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    start = int(day.timestamp())
    end = start + 24 * 60 * 60 - 1
    return (start, end)


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
    incidents: list = None          # list[str] of YYYY-MM-DD
    pinned_rules: list = None       # list[dict{pattern, warning, critical}]
    set_labels: list = None         # list[tuple(metric_glob_or_None, label, value)]
    days_back: int = 7              # lookback window for the baseline query
    expr_rewrites: dict = None      # dict[alert_name -> new_expr]; applied in-memory before tuning

    def __post_init__(self):
        if self.incidents is None:
            self.incidents = []
        if self.pinned_rules is None:
            self.pinned_rules = []
        if self.set_labels is None:
            self.set_labels = []
        if self.expr_rewrites is None:
            self.expr_rewrites = {}


@dataclass
class RuleOutcome:
    rule_name: str
    status: str                     # "tuned" | "skipped" | "filtered" | "pinned"
    reason: Optional[str] = None    # populated for skipped/filtered/pinned
    old_warning: Optional[float] = None
    old_critical: Optional[float] = None
    new_warning: Optional[float] = None
    new_critical: Optional[float] = None
    percentile_value: Optional[float] = None
    sample_count: Optional[int] = None
    operator: Optional[str] = None
    incident_coverage: Optional[list] = None   # list[dict] per incident
    pinned_pattern: Optional[str] = None       # which policy pattern matched


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
    def pinned_count(self) -> int:
        return sum(1 for o in self.outcomes if o.status == "pinned")

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

    def __init__(self, axonops, args, config: TuneAlertsConfig):
        self.axonops = axonops
        self.args = args
        self.config = config
        self.filter = RuleFilter(
            include=config.include,
            exclude=config.exclude,
            rules=config.rules,
        )
        # Cached label-probe helper. Used to explain 0-series query results
        # ("insufficient data" -> "broken_schema: label X has 0 values"); the
        # cache lives for the duration of a single tune run.
        self.schema = SchemaDiagnostic(axonops, args)
        # Counts log/event records for `events{...}` rules via the dedicated
        # search endpoint (metrics query_range 500s on these). Lets us tune
        # event-shape rules from observed rate instead of skipping them.
        self.events = EventsQuerier(axonops, args)

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

    def fetch_from_api(self) -> dict:
        """Fetch alert_rules.json directly from the AxonOps API."""
        url = ALERT_RULES_URL.format(
            org=self.args.org,
            cluster_type=self.axonops.get_cluster_type(),
            cluster=self.args.cluster,
        )
        data = self.axonops.do_request(url=url, method="GET") or {}
        if "metricrules" not in data or not isinstance(data["metricrules"], list):
            raise ValueError("Fetched API response missing 'metricrules' list")
        return data

    # ---- main orchestration ----

    def tune_all(self, input_json: dict) -> TuneRunResult:
        cluster_name = input_json.get("name") or self.args.cluster
        tuned_json = deepcopy(input_json)

        end_ts = int(time.time())
        start_ts = end_ts - self.config.days_back * 86400

        # Apply declarative expr rewrites BEFORE tuning so the metric query,
        # the percentile computation, the policy-pin expr rewrite, and the
        # output JSON all see the same corrected expr. Warn — but don't fail
        # — on rewrites that don't match a rule (the rule may have been
        # renamed or removed since the rewrites file was authored).
        if self.config.expr_rewrites:
            self._apply_expr_rewrites(tuned_json)

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

        if not self.filter.accepts(name):
            return RuleOutcome(
                rule_name=name, status="filtered", reason="excluded by filter",
                old_warning=old_warning, old_critical=old_critical,
            )

        # Policy-pin stage: if the rule matches a pinned pattern, apply the
        # fixed values and skip the whole tuning pipeline (no metric query,
        # no percentile computation, no sanity clamps). Pinned values are
        # policy — the caller knows the right number.
        pin = self._find_pinned(name)
        if pin is not None:
            pinned_pattern, pinned_warning, pinned_critical = pin
            # The literal string "shipped" resolves to the rule's current
            # value at apply time. Lets policy entries document "pin at
            # whatever the rule currently has" without restating numbers.
            if pinned_warning == "shipped":
                pinned_warning = old_warning
            if pinned_critical == "shipped":
                pinned_critical = old_critical
            try:
                _bare, operator, _old = ExprRewriter.strip_threshold(expr)
                # Expr has a trailing threshold — rewrite it in lockstep with
                # the JSON warningValue/criticalValue so they don't drift.
                rule["expr"] = ExprRewriter.rewrite(expr, new_warning=pinned_warning)
            except ValueError as e:
                # Log-pattern event rules (`events{message="..."}`) carry their
                # threshold only in the rule's JSON `operator`/`warningValue`/
                # `criticalValue` fields — there's nothing to strip from the
                # expr. Pin via the JSON fields and leave expr alone. For any
                # other unparseable expr, surface the original skip so latent
                # rule bugs aren't masked by a silent pin.
                if not _is_event_metric_rule(expr):
                    return RuleOutcome(
                        rule_name=name, status="skipped",
                        reason=f"cannot parse expr for pinning: {e}",
                        old_warning=old_warning, old_critical=old_critical,
                        pinned_pattern=pinned_pattern,
                    )
                operator = rule.get("operator", "")
            rule["warningValue"] = pinned_warning
            rule["criticalValue"] = pinned_critical
            return RuleOutcome(
                rule_name=name, status="pinned",
                reason=f"matched policy pattern {pinned_pattern!r}",
                old_warning=old_warning, old_critical=old_critical,
                new_warning=pinned_warning, new_critical=pinned_critical,
                operator=operator, pinned_pattern=pinned_pattern,
            )

        # `events{...}` rules can't go through query_range (the metrics
        # backend 500s on the events series) but the dedicated /events
        # search endpoint can count them. Try the events path first; only
        # fall back to the original short-circuit if the endpoint is
        # unreachable or the expr doesn't parse into recognised filters.
        if _is_event_metric_rule(expr):
            event_outcome = self._tune_event_rule(
                rule, start_ts=start_ts, end_ts=end_ts,
            )
            if event_outcome is not None:
                return event_outcome
            return RuleOutcome(
                rule_name=name, status="skipped",
                reason="event/log-shape rule (events metric, not workload-tunable)",
                old_warning=old_warning, old_critical=old_critical,
            )

        try:
            bare, operator, _old_str = ExprRewriter.strip_threshold(expr)
        except ValueError as e:
            return RuleOutcome(
                rule_name=name, status="skipped", reason=f"cannot parse expr: {e}",
                old_warning=old_warning, old_critical=old_critical,
            )

        # Apply caller-supplied label pins to the QUERY expression only — the
        # stored rule expr is left as-is. Lets the tuner sample real workload
        # data when the shipped selector targets a broken multi-value list.
        query_expr = bare
        for metric_glob, label, value in self.config.set_labels:
            query_expr = ExprRewriter.set_label(query_expr, label, value, metric_glob)
        # Drop placeholder empty matchers so query_range stops 500'ing on them.
        query_expr = ExprRewriter.drop_empty_matchers(query_expr)

        # Build the list of incident windows
        incident_windows = [_incident_day_range(d) for d in self.config.incidents]

        querier = MetricQuerier(self.axonops, self.args)

        # Baseline: either a single 7-day query (no incidents) or multiple
        # sub-range queries skipping over each incident window.
        try:
            if incident_windows:
                baseline_samples = self._baseline_samples_excluding(
                    querier, query_expr, start_ts, end_ts, incident_windows,
                )
            else:
                baseline_samples = querier.query(query_expr, start=start_ts, end=end_ts, step="1m")
        except HTTPCodeError as e:
            return RuleOutcome(
                rule_name=name, status="skipped", reason=f"query failed: {e}",
                old_warning=old_warning, old_critical=old_critical, operator=operator,
            )

        if len(baseline_samples) < self.config.min_samples:
            # When the query returned LITERALLY zero series, the most likely
            # cause is a label-schema break (rule filters on a label the
            # cluster doesn't emit) rather than a genuine "no traffic"
            # situation. Probe the cluster's actual label values and report
            # the offending label; fall back to the generic message when no
            # schema break is found or the probe endpoint isn't usable.
            reason = f"insufficient data ({len(baseline_samples)} samples)"
            if len(baseline_samples) == 0:
                diag = self.schema.diagnose(query_expr)
                if diag:
                    reason = diag
            return RuleOutcome(
                rule_name=name, status="skipped",
                reason=reason,
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

        # Percent-metric clamp: if the expression ends with `* 100`
        # (the idiomatic Prometheus percentage-conversion pattern) AND
        # the original thresholds were in the 0–100 range, clamp the
        # tuned values so we never emit a nonsensical threshold like
        # 101.44% disk usage. Skipped when either original threshold
        # already exceeds 100 — in that case the metric is probably not
        # a bounded percentage after all.
        if _looks_like_percentage(bare, old_warning, old_critical):
            new_warning = min(new_warning, 100.0)
            new_critical = min(new_critical, 100.0)

        incident_coverage = []

        # Incident coverage: for each incident, check whether the baseline-derived
        # threshold would fire, and adjust downward (for >=/>) or upward (for <=/<)
        # if the metric reflected the incident but threshold would miss.
        for window in incident_windows:
            inc_start, inc_end = window
            # Snapshot values BEFORE any potential adjustment this iteration
            pre_warning = new_warning
            pre_critical = new_critical
            try:
                incident_samples = querier.query(query_expr, start=inc_start, end=inc_end, step="1m")
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
                entry["action"] = f"critical {_format_value(pre_critical)} → {_format_value(adjusted_critical)}"

            incident_coverage.append(entry)

        # Sanity clamps
        if new_warning <= 0 or new_critical <= 0:
            return RuleOutcome(
                rule_name=name, status="skipped",
                reason=f"nonsensical (new warning={new_warning}, critical={new_critical})",
                old_warning=old_warning, old_critical=old_critical, operator=operator,
                sample_count=calc.sample_count, incident_coverage=incident_coverage,
            )

        try:
            warning_unreasonable = self._unreasonable_delta(old_warning, new_warning)
            critical_unreasonable = self._unreasonable_delta(old_critical, new_critical)
        except ValueError as e:
            return RuleOutcome(
                rule_name=name, status="skipped",
                reason=f"cannot evaluate delta: {e}",
                old_warning=old_warning, old_critical=old_critical,
                operator=operator, sample_count=calc.sample_count,
                incident_coverage=incident_coverage,
            )

        if warning_unreasonable or critical_unreasonable:
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
        from axonopscli.utils import HTTPCodeError

        sorted_windows = sorted(incident_windows)
        cursor = start_ts
        baseline = []
        sub_ranges_completed = 0
        ranges_to_query = []
        for inc_start, inc_end in sorted_windows:
            if inc_end < start_ts or inc_start > end_ts:
                continue
            clipped_start = max(inc_start, start_ts)
            clipped_end = min(inc_end, end_ts)
            if cursor < clipped_start:
                ranges_to_query.append((cursor, clipped_start - 1))
            cursor = max(cursor, clipped_end + 1)
        if cursor <= end_ts:
            ranges_to_query.append((cursor, end_ts))

        for r_start, r_end in ranges_to_query:
            try:
                baseline.extend(querier.query(promql, start=r_start, end=r_end, step="1m"))
                sub_ranges_completed += 1
            except HTTPCodeError as e:
                raise HTTPCodeError(
                    f"{e} (after collecting {len(baseline)} samples from "
                    f"{sub_ranges_completed}/{len(ranges_to_query)} sub-ranges)"
                )
        return baseline

    def _apply_expr_rewrites(self, tuned_json: dict) -> None:
        """Rewrite rule exprs in-place per ``config.expr_rewrites``.

        Matches on the rule's ``alert`` name (exact match, not glob — these
        are surgical, not pattern-based). A no-op rewrite (new expr ==
        current expr) is silently skipped so re-runs don't churn. Any
        rewrite whose ``alert`` doesn't appear in the input emits a stderr
        warning so misnamed entries don't sit silent.
        """
        rewrites = dict(self.config.expr_rewrites)
        applied = 0
        for rule in tuned_json.get("metricrules", []):
            name = rule.get("alert")
            if name in rewrites:
                new_expr = rewrites.pop(name)
                if rule.get("expr", "").strip() != new_expr.strip():
                    rule["expr"] = new_expr
                    applied += 1
        if rewrites:
            for name in rewrites:
                print(
                    f"WARNING: expr_rewrites entry for {name!r} did not match any rule",
                    file=sys.stderr,
                )
        if applied:
            print(f"Applied {applied} expr rewrite(s) in-memory", file=sys.stderr)

    def _tune_event_rule(self, rule: dict, start_ts: int, end_ts: int):
        """Tune a rule whose expr is `events{...}` by counting log/event
        records through the dedicated /events search endpoint.

        The events store is a separate backend; metrics query_range 500s
        on these queries. We POST the selector and read
        ``metadata._count`` as the total over the window, then derive a
        per-``for``-window threshold heuristic for the operator.

        Returns:
          * ``RuleOutcome(status="tuned"|"pinned")`` on success.
          * ``None`` if the endpoint isn't usable or the expr filters
            can't be parsed — caller falls back to the legacy "event/
            log-shape rule" skip.

        Threshold heuristic (operator-friendly, intentionally
        conservative):

        - Let ``mean = count * for_min / window_min`` (expected events
          per ``for`` window).
        - When ``mean < 0.01`` (under 1 event per 100 windows): the rule
          is "any occurrence is bad" — pin at the rule's current values,
          status=``pinned``.
        - Otherwise: ``warn = max(shipped_warn, ceil(mean * 5))`` and
          ``crit = max(shipped_crit, ceil(warn * 2))``. The 5× factor
          approximates p99 of a Poisson with low mean; the operator can
          still override via policy. Status=``tuned``.

        The total count goes into ``sample_count`` so the audit report
        carries the observed evidence next to every event rule.
        """
        name = rule.get("alert", "<unnamed>")
        expr = rule.get("expr", "")
        operator = rule.get("operator", "")
        old_warning = rule.get("warningValue")
        old_critical = rule.get("criticalValue")

        filters = EventsQuerier.parse_filters(expr)
        if not filters and expr.strip() != "events{}":
            # Unrecognisable shape — let the caller fall back.
            return None

        count = self.events.count(filters, start=start_ts, end=end_ts)
        if count is None:
            return None

        for_min = _for_to_minutes(rule.get("for"))
        window_min = max(1.0, (end_ts - start_ts) / 60.0)
        mean_per_window = count * for_min / window_min

        try:
            old_w_f = float(old_warning) if old_warning is not None else 0.0
            old_c_f = float(old_critical) if old_critical is not None else 0.0
        except (TypeError, ValueError):
            old_w_f = old_c_f = 0.0

        if mean_per_window < 0.01:
            # Rare enough that the shipped tight value is correct; pin.
            rule["warningValue"] = old_warning
            rule["criticalValue"] = old_critical
            return RuleOutcome(
                rule_name=name, status="pinned",
                reason=(f"events: {count} occurrence(s) in {self.config.days_back}d "
                        f"(mean/for-window={mean_per_window:.4f}); shipped sufficient"),
                old_warning=old_warning, old_critical=old_critical,
                new_warning=old_warning, new_critical=old_critical,
                operator=operator, sample_count=count,
                percentile_value=mean_per_window,
            )

        new_warning = max(old_w_f, math.ceil(mean_per_window * 5))
        new_critical = max(old_c_f, math.ceil(new_warning * 2))

        if new_warning == old_w_f and new_critical == old_c_f:
            status = "pinned"
            reason = (f"events: {count} in {self.config.days_back}d; observed rate "
                      f"({mean_per_window:.2f}/for-window) under shipped threshold")
        else:
            status = "tuned"
            reason = None

        rule["warningValue"] = new_warning
        rule["criticalValue"] = new_critical
        return RuleOutcome(
            rule_name=name, status=status, reason=reason,
            old_warning=old_warning, old_critical=old_critical,
            new_warning=new_warning, new_critical=new_critical,
            operator=operator, sample_count=count,
            percentile_value=mean_per_window,
        )

    def _find_pinned(self, rule_name: str):
        """Return (pattern, warning, critical) for the first matching pinned
        entry, or None. Uses fnmatch glob matching on rule names."""
        for entry in self.config.pinned_rules:
            pattern = entry.get("pattern")
            if pattern and fnmatch.fnmatchcase(rule_name, pattern):
                return (pattern, entry["warning"], entry["critical"])
        return None

    def _unreasonable_delta(self, old_val, new_val) -> bool:
        """Returns True if the magnitude change is unreasonable.

        Raises ValueError if old_val is not coercible to float (caller should
        skip the rule with a clear reason rather than silently tuning with
        garbage).
        """
        if old_val is None:
            return False  # first tune; no baseline to compare
        try:
            old_f = float(old_val)
        except (TypeError, ValueError) as e:
            raise ValueError(f"unparseable old threshold {old_val!r}: {e}")
        try:
            new_f = float(new_val)
        except (TypeError, ValueError):
            return True  # treat unparseable new value as unreasonable
        if old_f == 0:
            return False
        ratio = max(abs(new_f / old_f), abs(old_f / new_f))
        return ratio > self.config.max_delta

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
        if result.pinned_count:
            summary_parts.append(f"pinned {result.pinned_count}")
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
        elif o.status == "pinned":
            print(
                f"  [pinned]   {o.rule_name}: "
                f"warning {o.old_warning}→{o.new_warning}, "
                f"critical {o.old_critical}→{o.new_critical} "
                f"(policy pattern {o.pinned_pattern!r})"
            )

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
            f"**Window:** {window_start} → {window_end} ({self.config.days_back} days)",
        ]
        if self.config.set_labels:
            overrides = ", ".join(
                f"{(g + ':') if g else ''}{label}='{value}'"
                for g, label, value in self.config.set_labels
            )
            lines.append(f"**Query label overrides:** {overrides}")
        lines += [
            "",
            "## Summary",
            "",
            f"- Tuned: {result.tuned_count} rules",
            f"- Pinned (policy override): {result.pinned_count} rules",
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
                    f"| {_md_cell(o.rule_name)} | {_md_cell(o.operator)} | "
                    f"{_md_cell(o.old_warning)} → {_md_cell(o.new_warning)} | "
                    f"{_md_cell(o.old_critical)} → {_md_cell(o.new_critical)} | "
                    f"{_md_cell(_format_value(o.percentile_value))} | {_md_cell(o.sample_count)} |"
                )
            lines.append("")

        skipped = [o for o in result.outcomes if o.status == "skipped"]
        if skipped:
            lines.extend(["## Skipped rules", "", "| Rule | Reason |", "|---|---|"])
            for o in skipped:
                lines.append(f"| {_md_cell(o.rule_name)} | {_md_cell(o.reason)} |")
            lines.append("")

        pinned = [o for o in result.outcomes if o.status == "pinned"]
        if pinned:
            lines.extend([
                "## Pinned rules (policy override)",
                "",
                "| Rule | Op | warning (old → new) | critical (old → new) | Policy pattern |",
                "|---|---|---|---|---|",
            ])
            for o in pinned:
                lines.append(
                    f"| {_md_cell(o.rule_name)} | {_md_cell(o.operator)} | "
                    f"{_md_cell(o.old_warning)} → {_md_cell(o.new_warning)} | "
                    f"{_md_cell(o.old_critical)} → {_md_cell(o.new_critical)} | "
                    f"{_md_cell(o.pinned_pattern)} |"
                )
            lines.append("")

        filtered = [o for o in result.outcomes if o.status == "filtered"]
        if filtered:
            lines.extend(["## Filtered rules", "", "| Rule | Reason |", "|---|---|"])
            for o in filtered:
                lines.append(f"| {_md_cell(o.rule_name)} | {_md_cell(o.reason)} |")
            lines.append("")

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
                        f"| {_md_cell(rule_name)} | {_md_cell(entry['status'])} | "
                        f"{_md_cell(_format_value(entry.get('peak')))} | {_md_cell(entry['action'])} |"
                    )
                lines.append("")

        return "\n".join(lines)


def _round_threshold(v: float):
    """Round to int if whole, else 2 decimals. Keeps JSON idiomatic."""
    rounded = round(v, 2)
    if rounded == int(rounded):
        return int(rounded)
    return rounded
