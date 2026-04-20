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


import json
import os
import time
from copy import deepcopy
from datetime import datetime, timezone, timedelta


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

    def __post_init__(self):
        if self.incidents is None:
            self.incidents = []


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
    incident_coverage: Optional[list] = None   # list[dict] per incident


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

    ALERT_RULES_URL = "/api/v1/alert-rules/{org}/{cluster_type}/{cluster}"

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
        url = self.ALERT_RULES_URL.format(
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

        return "\n".join(lines)


def _round_threshold(v: float):
    """Round to int if whole, else 2 decimals. Keeps JSON idiomatic."""
    rounded = round(v, 2)
    if rounded == int(rounded):
        return int(rounded)
    return rounded
