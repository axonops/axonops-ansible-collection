# Design: `axonopscli tune-alerts`

**Date:** 2026-04-17
**Status:** Approved (pending spec review)
**Repo:** `axonops-ansible-collection`
**Scope:** Add a new CLI subcommand that reads an exported `alert_rules.json`, queries the last 7 days of each metric rule's data from AxonOps, and writes a tuned sibling JSON plus a markdown audit report. Thresholds calibrated to observed workload + headroom. Two follow-up commits: `--from-api` auto-fetch and `--incident DATE` postmortem-driven tuning.

## Problem

Alert thresholds in a typical AxonOps deployment are set once and drift from reality. Teams want alerts that reflect the *current* workload: if the system ran cleanly for the past week, thresholds should sit just above that observed ceiling with some headroom, so genuine degradation is caught while false positives stay low. Today there is no tooling to do this — operators either leave defaults or hand-tune after an incident.

## Goal

A one-command tuner that takes an exported `alert_rules.json` and produces a tuned variant calibrated to the last 7 days of observed behavior, with a human-readable audit report for review before re-apply. Optionally can auto-fetch from the API, and optionally can exclude specific incident windows from the baseline while verifying the tuned thresholds *would* have caught those incidents.

## Non-goals

- `for` (duration) tuning — thresholds only
- Per-filter tuning (per-DC / per-rack / per-host) — global query for v1
- Log rules / event rules tuning — different conceptual model
- In-place modification of the input JSON — always writes a sibling file
- Pushing tuned rules back to the server — user re-applies via the existing Ansible role
- Historical comparison across tuning runs — each run independent
- Time-range incident windows — whole-UTC-day granularity only for v1
- Duration-aware "would have fired" verification — simple max/min for v1

## Core algorithm

Percentile-based with headroom, operator-direction aware.

**For `>=` / `>` operators (high values are bad):**

```
threshold = percentile(samples, P) × (1 + headroom)
```

**For `<=` / `<` operators (low values are bad):**

```
threshold = percentile(samples, 100-P) × (1 - headroom)
```

Where `P` and `headroom` come from a profile preset or individual CLI flags.

### Profile presets

| Profile   | Percentile | Warning headroom | Critical headroom |
|-----------|------------|------------------|-------------------|
| `noisy`   | p95        | +5%              | +10%              |
| `default` | p99        | +10%             | +20%              |
| `quiet`   | p99.9      | +20%             | +50%              |

Individual flags `--percentile`, `--warning-headroom`, `--critical-headroom` override profile values.

## Decisions table

| Decision | Choice | Why |
|---|---|---|
| Algorithm shape | `percentile × (1 + headroom)` | Tracks actual workload with explicit safety margin. Easy to reason about. |
| Profile names | `noisy` / `default` / `quiet` | Per user: intuitive, operationally meaningful. |
| Configurability | Profile + individual flag overrides | Profile for ergonomics, flags for power users. |
| Direction inversion | Automatic from `operator` | `<`/`<=` rules mean "lower is worse"; flip the tail. |
| Scope | `metricrules` only | Only numeric-threshold rules can be tuned by this algorithm. |
| Filters | `--include`, `--exclude`, `--rule NAME` | Enable iterative/targeted tuning. |
| Tune direction | Both (lower OR raise) | Goal is "track actual workload" — stale high thresholds miss real degradations. |
| Min samples | 100 (configurable `--min-samples`) | Below this, percentile estimates are statistically unreliable. |
| Skipped rule handling | Preserve unchanged in output; list in stdout summary + audit report | Clean JSON schema; full visibility elsewhere. |
| Sanity clamps | Hard floor (skip if ≤0) + soft ratio (skip if `|new/old| > max_delta`, default 10, configurable) | ≤0 is nonsensical; huge deltas signal instability or bug. |
| CLI shape | New top-level subcommand `tune-alerts` | Single-purpose verb; matches existing pattern. |
| Input | `--input PATH` required for v1 | Explicit audit trail — user inspects the source JSON before tuning. |
| Auto-fetch | `--from-api` flag (commit 7, follow-up) | Skip the separate export step when iterating. |
| Output filename | `alert_rules.tuned.for.<cluster>.json` next to input | Per user spec. Cluster from JSON `name` field, fallback `--cluster`. |
| File mode | 0600 | Same as export feature; audit-report files are 0644. |
| Transparency | Always: stdout summary + sidecar `.report.md`; `-v` adds per-rule detail | Ergonomic default, deep audit available. |
| Metrics API | `GET /api/v1/query_range` (Prometheus-compatible) | Confirmed from axon-dash proxy. |
| Query window | Fixed 7 days, step 1m | Per user request. `--window` flag deferred. |
| Incident flag | `--incident YYYY-MM-DD` (repeatable, commit 8) | Full UTC day granularity. Excludes from baseline, verifies coverage, adjusts if needed. |

## CLI surface

```
axonopscli --org X --cluster bc1 [--cluster-type cassandra] \
    [--token Z | --username U --password P] [--url URL] \
    tune-alerts \
        --input ./exported/alert_rules.json \
        [--profile {noisy,default,quiet}]     (default: default)
        [--percentile FLOAT]                   (override profile; 0<P<100)
        [--warning-headroom FLOAT]             (override profile; e.g. 0.10)
        [--critical-headroom FLOAT]            (override profile; e.g. 0.20)
        [--min-samples N]                      (default: 100)
        [--max-delta N]                        (default: 10)
        [--include GLOB] [--exclude GLOB]      (repeatable; applied in order: include-then-exclude)
        [--rule NAME]                          (repeatable; exact-match, implies --include)
        [--from-api]                           (commit 7; auto-fetch instead of --input)
        [--incident YYYY-MM-DD]                (commit 8; repeatable)
```

Exit codes: 0 on success (including "all rules skipped"), non-zero on auth failure, malformed input JSON, or I/O errors.

## Architecture

New file `cli/axonopscli/components/tune_alerts.py` containing four small independently-testable classes:

### `MetricQuerier`

Thin wrapper over `axonops.do_request` targeting `/api/v1/query_range`. Takes a query string + `(start, end, step)` and returns a flat list of numeric samples (nulls/NaN filtered out). Owns only the HTTP and response-flattening logic.

```python
class MetricQuerier:
    QUERY_RANGE_URL = "/api/v1/query_range/{org}/{cluster_type}/{cluster}"

    def __init__(self, axonops, args): ...

    def query(self, promql, start, end, step="1m") -> list[float]:
        """Returns flat list of non-null numeric samples from all series."""
```

Note: the exact URL path template will be verified at implementation time against an actual AxonOps response. If the base path is different (e.g., no org/cluster-type embedded), the format string is trivially adjustable. This is called out in the plan's Task 3.

### `ThresholdCalculator`

Pure function. Given `samples, operator, profile_config` returns a `TuneResult` dataclass holding `new_warning`, `new_critical`, plus diagnostics (`percentile_value`, `sample_count`). Direction-aware (inverts for `<`/`<=`). No I/O.

```python
class ThresholdCalculator:
    @staticmethod
    def compute(samples, operator, percentile, warning_headroom, critical_headroom) -> TuneResult:
        ...
```

### `ExprRewriter`

Pure function. Given `expr` string + new warning value, strips the trailing ` <operator> <value>` (reusing the `re.sub(' [^ ]+ [^ ]+$', '', expr)` pattern already used by the Ansible `alert_rule.py` module) and emits `{bare_metric} {operator} {new_value}`. Preserves operator verbatim.

```python
class ExprRewriter:
    @staticmethod
    def strip_threshold(expr) -> tuple[str, str, str]:
        """Returns (bare_metric, operator, old_value_str)."""

    @staticmethod
    def rewrite(expr, new_warning) -> str:
        """Returns new expr with threshold replaced."""
```

### `TuneAlertsOrchestrator`

Orchestration — reads input JSON, iterates `metricrules`, applies filters, calls the three helpers, applies sanity clamps and incident checks (commit 8), writes JSON + sidecar report.

```python
class TuneAlertsOrchestrator:
    def __init__(self, axonops, args, config): ...
    def load_input(self) -> dict: ...
    def tune_all(self, input_json) -> TuneRunResult: ...
    def write_output(self, input_path, cluster_name, result): ...
    def write_audit_report(self, input_path, cluster_name, result): ...
    def print_summary(self, result): ...
```

`TuneRunResult` holds per-rule outcomes (tuned / skipped with reason / diagnostics) and aggregate counts.

### `application.py` wiring

New subparser block after the `alerts` subparser, calling a new `run_tune_alerts` handler. Top-level import of `TuneAlertsOrchestrator`. Scrubs `--token` and `--password` from verbose output using the existing `_scrubbed_args` helper.

## Data flow

```
$ axonopscli --org X --cluster bc1 tune-alerts --input ./exported/alert_rules.json

1. Load input JSON; assert shape (top-level `name`, `metricrules[]`).
2. Resolve cluster_name = input["name"] or args.cluster.
3. end_ts = now (UTC); start_ts = end_ts - 7 days.
4. For each rule in metricrules:
     a. If filtered out by --include/--exclude/--rule → mark "filtered".
     b. bare_metric, operator, old_value = ExprRewriter.strip_threshold(rule.expr).
     c. samples = MetricQuerier.query(bare_metric, start_ts, end_ts, step=1m).
        ↳ If len(samples) < min_samples → mark "insufficient data".
        ↳ If HTTP error → mark "query failed: <err>".
     d. (Commit 8) If --incident set and any incident day overlaps:
           - Exclude those samples from baseline computation.
           - Query incident samples separately → `incident_samples`.
     e. result = ThresholdCalculator.compute(samples, operator, ...).
     f. (Commit 8) If --incident set and metric was impacted:
           - Verify incident_peak would have fired new_critical (and new_warning).
           - If not: lower (or raise) thresholds per "Incident coverage" rules below.
     g. Sanity clamps:
           - If new_warning ≤ 0 or new_critical ≤ 0 → mark "nonsensical".
           - If |new_warning/old_warning| > max_delta → mark "unreasonable delta".
           - Same for critical.
     h. Apply: rule.warningValue = new_warning;
              rule.criticalValue = new_critical;
              rule.expr = ExprRewriter.rewrite(rule.expr, new_warning).
              Mark "tuned" with diagnostics.
5. Write tuned JSON to ./exported/alert_rules.tuned.for.bc1.json (mode 0600).
6. Write audit report to ./exported/alert_rules.tuned.for.bc1.report.md (mode 0644).
7. Print stdout summary; if -v, per-rule details.
8. Exit 0.
```

## Incident coverage logic (commit 8)

For each `--incident YYYY-MM-DD`:

1. Determine window: `[YYYY-MM-DD 00:00:00Z, YYYY-MM-DD 23:59:59.999Z]`.
2. Exclude samples in any incident window from the baseline percentile computation.
3. Query incident-window samples separately per rule.
4. After baseline-derived `new_warning` / `new_critical`:
    - `incident_peak` = max (for `>=`/`>`) or min (for `<=`/`<`) of incident samples.
    - **Case A — baseline-derived threshold would fire**: if, for `>=`: `incident_peak >= new_critical`, or for `<=`: `incident_peak <= new_critical` — no adjustment. Log "Yes (baseline)".
    - **Case B — threshold would miss, but metric reflected the incident**: if `incident_peak` exceeds the non-incident baseline normal (i.e., falls outside `percentile(non_incident_samples, P)`), adjust:
        - For `>=`/`>`: `new_critical = min(new_critical, incident_peak × 0.95)`; same ratio applied to warning proportionally.
        - For `<=`/`<`: `new_critical = max(new_critical, incident_peak × 1.05)`; same for warning.
        Log "Yes (adjusted)".
    - **Case C — metric wasn't impacted by this incident**: defined precisely as: for `>=`/`>`: `incident_peak <= percentile(non_incident_samples, P)`; for `<=`/`<`: `incident_peak >= percentile(non_incident_samples, 100-P)`. In other words, the incident's worst observation is no worse than a typical non-incident observation at the same percentile — meaning the metric didn't reflect the incident. Don't adjust; log "metric not impacted by incident".

Audit report gains a per-incident "Incident coverage" section.

**Trade-off acknowledged:** v1 uses single-sample max/min, not `for`-duration-aware sustained violation. Real AxonOps fires on sustained threshold violation. This v1 overestimates detection capability; acceptable starting point, upgradable later.

## Audit report format

`alert_rules.tuned.for.<cluster>.report.md` (mode 0644):

```markdown
# Alert tuning report — <cluster>

**Generated:** 2026-04-17T15:30:00Z
**Source:** ./exported/alert_rules.json
**Profile:** default (p99, warning +10%, critical +20%)
**Window:** 2026-04-10T15:30:00Z → 2026-04-17T15:30:00Z (7 days)
**Incident windows excluded from baseline:** 2026-04-12  (commit 8 only)

## Summary
- Tuned: 42 rules
- Skipped: 3 rules (insufficient data: 2, nonsensical: 1)

## Tuned rules

| Rule | Op | warning (old → new) | critical (old → new) | p99 | Samples | Notes |
|---|---|---|---|---|---|---|
| GC duration - G1 YoungGen | >= | 1000 → 825 | 1300 → 900 | 750 | 10080 | |
| Avg IO wait CPU per Host  | >= | 50 → 44    | 70 → 87   | 40  | 10080 | critical adjusted for incident |
...

## Skipped rules

| Rule | Reason |
|---|---|
| NTP offset (milliseconds) | insufficient data (42 samples) |
| Metric X                  | nonsensical (new critical = 0) |
| Metric Y                  | unreasonable delta (new/old = 23×) |
...

## Incident coverage (2026-04-12)          [commit 8 only]

| Rule | Would have fired? | Incident peak | Action |
|---|---|---|---|
| GC duration - G1 YoungGen | Yes (baseline)  | 2100 | none |
| Avg IO wait CPU per Host  | Yes (adjusted)  | 92   | critical lowered 48 → 87 |
| NTP offset (milliseconds) | N/A             | 15   | metric not impacted by incident |
```

## Error handling

| Failure mode | Behavior |
|---|---|
| Input file missing / unreadable | Exit 1, clear message |
| JSON parse error | Exit 1, "malformed JSON at line N" |
| `metricrules` key missing or not a list | Exit 1, "unsupported format" |
| Auth error (first query) | Let `HTTPCodeError` propagate (fail fast, no per-rule retries) |
| Auth error (subsequent queries) | Treated same as fail fast — the credential isn't going to become valid |
| Single metric query fails (network blip, 500) | Skip that rule with reason, continue |
| All rules skipped | Still write (unchanged) JSON + report, exit 0 with prominent warning |
| Output directory unwritable | Exit 1 before writing |
| Output path exists as file not dir (for parent) | Exit 1 |

## Testing

Same `unittest` + `unittest.mock` pattern as existing components. No live API calls.

**`ThresholdCalculator`** (~12 tests)
- p99 with headroom produces expected value for `>=`
- Direction inversion for `<` (p1 with negative headroom)
- Profile presets: noisy, default, quiet round-trip correctly
- Individual flag overrides profile
- Single-sample case (numpy-free percentile arithmetic)
- All-zeros samples → returns (0, 0) — caller responsible for sanity clamp
- NaN/null filtering: calculator expects pre-cleaned input
- Headroom = 0 → no headroom applied
- Unusual percentiles (p50 = median) work

**`ExprRewriter`** (~6 tests)
- Simple: `foo >= 10` → `foo >= 20`
- With functions: `rate(foo[5m]) > 100` → `rate(foo[5m]) > 200`
- With `by` clause: `avg(foo) by (host) >= 50` → `avg(foo) by (host) >= 60`
- With multiplication: `abs(foo) * 1000 >= 100` → `abs(foo) * 1000 >= 120`
- Integer vs float threshold values preserved
- Operator preserved (`<`, `<=`, `==`)

**`MetricQuerier`** (~4 tests)
- Correct URL and query params generated
- Flatten Prometheus response shape to flat samples list
- Filters nulls and NaN
- HTTP error propagates `HTTPCodeError`

**`TuneAlertsOrchestrator`** (~10 tests)
- Happy path tunes all rules
- Filter: `--rule` picks single rule
- Filter: `--include` with glob
- Filter: `--exclude` takes precedence
- Skip: insufficient samples
- Skip: unreasonable delta
- Skip: nonsensical (≤0)
- Skip: query failure
- Output: JSON has updated fields only on tuned rules
- Output: audit report contains expected sections

**`Application.run_tune_alerts`** (~2 e2e tests)
- End-to-end with mocked `AxonOps.do_request`, verify output files
- Verbose mode scrubs token/password

**Commit 7 — `--from-api`** (~3 tests)
- Flag causes GET to `/api/v1/alert-rules/...`
- Omits `--input` argument validation error when neither set
- Error if both `--input` and `--from-api` set

**Commit 8 — `--incident`** (~6 tests)
- Incident date excluded from baseline sample set
- Incident peak verification: baseline threshold catches, no adjust
- Incident peak verification: metric impacted, threshold adjusted
- Incident peak verification: metric not impacted, no adjust
- Audit report "Incident coverage" section present
- Multiple incident dates handled

**Total: ~43 tests across all commits.**

## Commit breakdown

Atomic, independently revertible:

1. `feat(cli): add ThresholdCalculator for alert tuning` — pure helper + tests
2. `feat(cli): add ExprRewriter for alert tuning` — pure helper + tests
3. `feat(cli): add MetricQuerier for /api/v1/query_range` — HTTP wrapper + tests
4. `feat(cli): add TuneAlertsOrchestrator` — orchestration + filters + sanity clamps + audit report + tests
5. `feat(cli): wire tune-alerts CLI subcommand` — argparse + `run_tune_alerts` + e2e tests
6. `docs(cli): document tune-alerts in README`
7. `feat(cli): add --from-api flag to tune-alerts` — auto-fetch alternative to `--input`
8. `feat(cli): add --incident flag to tune-alerts` — postmortem-driven tuning

## Open questions / known limitations

1. **v1 uses max/min for incident coverage, not duration-aware.** Acknowledged trade-off; noted in audit report and release notes.
2. **If the past week was itself problematic (undetected ongoing degradation), baseline + headroom calibrates too high.** Mitigation: user reviews audit report before re-applying; can use `--warning-headroom 0 --critical-headroom 0` to disable headroom.
3. **The `/api/v1/query_range` URL template** is assumed from axon-dash proxy evidence; exact path will be verified during Task 3 implementation and adjusted if needed.
4. **No historical tuning comparison.** Each run independent. If this becomes valuable, add later.

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| `/api/v1/query_range` URL shape differs per auth mode | Medium | Test against real endpoint during Task 3; adjust template |
| `ExprRewriter` trailing-threshold regex fails on exotic expressions | Medium | Tests cover the shapes seen in the real export; fall back to "cannot rewrite" skip if regex fails |
| Percentile arithmetic edge cases (tiny N, non-finite values) | Low | `ThresholdCalculator` tests specifically exercise these |
| Metric query returns huge payload → memory | Low | 7 days × 1m = ~10k samples per series. Even with many series per rule, manageable |
| Users treat tuning as "set and forget" | Low | Audit report explicitly names the window and profile; re-running is cheap |
