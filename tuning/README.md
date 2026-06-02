# `tuning/` — alert-tuning workflow

Thin convenience wrappers around `cli/axonops.py` and the
`axonops.axonops.configurations` Ansible role: seed the collection's default
alert rules onto a cluster, observe real metrics, fit thresholds to the
workload, push the tuned rules back.

This directory is **local-only** (gitignored). The scripts orchestrate
production-affecting actions; keep them as project-team tooling, not part of
the shipped collection.

All scripts require `AXONOPS_TOKEN` in the environment. The base URL is
auto-detected by `tuning/resolve-axonops-url` (shared cloud
`dash.axonops.cloud/<org>` first, falling back to dedicated-subdomain
`<org>.axonops.cloud/dashboard` on 404) — no `AXONOPS_URL` is needed unless
you want to pin it.

---

## Setting up a new customer

These are the steps from "you've been given a token and a cluster name" to
"the alerts are tuned to the workload." Each numbered step is a deliberate
operator action; nothing happens automatically.

```bash
export AXONOPS_TOKEN=...
```

### 1. Pre-flight checks

```bash
# Confirm the URL resolves and the token works
tuning/resolve-axonops-url <org> <cluster> cassandra

# Verify every shipped default rule references a chart that exists on the
# cluster. Surfaces chart-name mismatches before tuning/default-apply hits them.
tuning/chart-check <org> <cluster>
```

Then **probe the cluster's metric label schema** before assuming the shipped
defaults work — some clusters encode consistency into `scope` (e.g.
`scope='Read_LOCAL_ONE'`) and percentile into `function` (e.g.
`function='99thPercentile'`) rather than the shipped defaults' standard
`consistency=` / `percentile=` labels. Mismatched clusters will need an expr
patcher (see step 4). A quick probe:

```bash
END=$(date -u +%s); START=$((END - 3600))
curl -sS -H "Authorization: Bearer $AXONOPS_TOKEN" \
  --data-urlencode "query=cas_ClientRequest_Latency" \
  --data-urlencode "start=$START" --data-urlencode "end=$END" \
  --data-urlencode "step=300s" \
  -G "<base-url>/api/v1/query_range" \
| python3 -c "import json,sys; \
  d=json.loads(sys.stdin.read()); s=d.get('data',{}).get('result') or []; \
  print('label keys:', sorted(s[0]['metric'].keys()) if s else '<no data>'); \
  print('one series:', s[0]['metric'] if s else {})"
```

### 2. Write the customer config

Copy the template and fill it in:

```bash
cp tuning/customers/example.env tuning/customers/<name>.env
$EDITOR tuning/customers/<name>.env
```

Required keys: `ORG`, `CLUSTER`, `HOT_KEYSPACE`, `HOT_TABLE`. The hot table is
the one with the highest p99 read latency in `HOT_KEYSPACE` (find it in
the AxonOps UI under Cassandra → Tables, or via the `axonops` MCP tools).

Optional knobs (set only when needed): `DAYS`, `MIN_SAMPLES`, `MAX_DELTA`,
`EXTRA_SET_LABELS`, `EXPR_PATCHER`, `PRE_HOOKS`. See the comments in
`example.env` and the **Customer config** section below.

### 3. (If needed) Add chart-name overrides

If `tuning/chart-check` flagged missing charts, add corrections in
`tuning/overrides/<org>/metric_alert_rules.yml` and/or
`tuning/overrides/<org>/<cluster>/metric_alert_rules.yml` — see
**Per-client overrides**.

### 4. (If needed) Build a schema-fix patcher

If the schema probe in step 1 showed mismatched labels, you'll have rules
whose stored exprs filter on labels that don't exist. The pattern:

1. Write `tuning/patch-<name>-broken-exprs` — reads the latest export, rewrites
   the affected rules' `expr` fields to use the cluster's actual label
   schema, writes `alert_rules.schemafix.json`.
2. **Probe each corrected selector against `query_range` before baking it
   in.** Don't ship fixes you haven't confirmed return data.
3. Set `EXPR_PATCHER=patch-<name>-broken-exprs` in the customer's `.env` —
   `tuning/cycle-customer` then runs the script, applies its output, and
   re-exports before tuning, automatically.

### 5. Seed the defaults

```bash
tuning/default-apply <org> <cluster> --check    # preview; verify 0 failures
tuning/default-apply <org> <cluster>            # apply
```

`tuning/default-apply` is destructive — it pushes ~50 rules through the
Ansible role and changes live alerting state. Always preview with `--check`
first. On a clean check, expect `failed=0`; `changed` reflects rules whose
content differs from current cluster state.

### 6. Cycle and tune

```bash
tuning/cycle-customer <name>
```

This is idempotent — safe to re-run. It exports, runs any `EXPR_PATCHER` /
`PRE_HOOKS` you've configured, applies the patched JSON, re-exports, and
tunes. Cycles without a patcher collapse to just export + tune.

Read the audit:

```bash
$EDITOR cli/exported/<org>/<cluster>/alert_rules.tuned.for.<cluster>.report.md
```

The **Skipped** section is the part to read carefully. Patterns to watch
for — and what to do about each — are in **Reading the tune report** below.

### 7. Push the tuned thresholds back

```bash
tuning/apply-customer <name> --dry-run          # preview
tuning/apply-customer <name> --yes              # apply
```

The apply step's POST retries transient 5xx automatically.

### 8. Routine cycle, going forward

For ongoing tuning runs (e.g. after a workload shift, or after AxonOps
ships a release with new default rules):

```bash
tuning/default-apply <org> <cluster>            # only if defaults changed or rules drifted
tuning/cycle-customer <name>                    # always
tuning/apply-customer <name> --yes              # when you trust the report
```

`tuning/default-apply` clobbers any custom-expr patches the previous cycle
installed — that's why `tuning/cycle-customer` always runs after.

---

## Customer config — `tuning/customers/<name>.env`

Bash KEY=VALUE file the three customer-driven scripts source. One file per
customer.

| Key | Purpose | Required? |
|---|---|---|
| `ORG` / `CLUSTER` | AxonOps org and cluster names | yes |
| `HOT_KEYSPACE` / `HOT_TABLE` | Active keyspace and the hottest-read-latency table within it; the tune is retargeted at these so it sees representative workload | yes |
| `DAYS` | Lookback window in days (CLI default 7) | no |
| `MIN_SAMPLES` | Minimum samples per rule (CLI default 100) | no |
| `MAX_DELTA` | Maximum delta multiplier vs seeded default (CLI default 10) | no |
| `EXTRA_SET_LABELS` | Bash array of extra `--set-label` values, e.g. `("table=${HOT_TABLE}")` when the cluster's rules carry a separate `table` label on top of `keyspace=` and `cas_Table_*:scope=` | no |
| `EXPR_PATCHER` | Path (relative to `tuning/`) of a schema-fix patcher — only set if the cluster has a label-schema mismatch | no |
| `PRE_HOOKS` | Bash array of paths (relative to `tuning/`) of idempotent setup scripts run at the very start of `tuning/cycle-customer` (e.g. dashboard chart corrections) | no |

`tuning/customers/example.env` is the template — copy and edit.

---

## Scripts

### Customer-driven (source `tuning/customers/<name>.env`)

| Script | Purpose |
|--------|---------|
| `tuning/tune-customer <name>` | Runs `tuning/tune` with the customer's `ORG`, `CLUSTER`, `--set-label keyspace=…`, `--set-label cas_Table_*:scope=…`, and any tune knobs from `.env`. |
| `tuning/cycle-customer <name>` | Full reconciliation: pre-hooks → export → (optional patcher + apply + re-export) → tune. Idempotent. |
| `tuning/apply-customer <name>` | Pushes the tuned JSON back via `tuning/tuned-apply`. Takes `--dry-run` / `--yes` / etc. |

### Generic pipeline (take `<org> <cluster>`)

| Script | Purpose |
|--------|---------|
| `tuning/default-apply` | Seeds **default metric alerts** (`--tags metrics`) onto the cluster via the Ansible role. Merges per-client overrides at both org and cluster levels. Auto-detects the base URL. **Destructive — preview with `--check`.** |
| `tuning/default-apply-logs` | Same shape, seeds the **default log alerts** (`--tags log_alerts`). Independent of metric seeding. |
| `tuning/export` | Pulls live alert rules + integrations into a dated, immutable snapshot under `cli/exported/<org>/<cluster>/<UTC-timestamp>/`. `latest`, `alert_rules.json`, `integrations.json` are symlinks tracking the newest snapshot. Always `--include-secrets`. |
| `tuning/tune` | Runs `tune-alerts` against the exported `alert_rules.json`. Auto-applies the team policy at `cli/exported/tune-alerts-policy.json`. Writes `alert_rules.tuned.for.<cluster>.json` + a `.report.md` audit. |
| `tuning/tuned-apply` | POSTs a tuned JSON back via `apply-tuned-alerts`. The CLI retries transient 5xx automatically. |
| `tuning/chart-check` | Preflight: verifies every default rule's `chart` field exists on the cluster's dashboards. Catches chart-rename surprises before seeding fails. |
| `tuning/resolve-axonops-url` | Helper used internally by `tuning/default-apply*` to auto-detect dedicated-subdomain orgs (probes shared host first, falls back on 404). |

---

## Per-client overrides — `tuning/overrides/`

`tuning/default-apply` merges YAML overrides at **two levels** into the staged
Ansible config:

```
tuning/overrides/<org>/metric_alert_rules.yml             → merged into org-level YAML
tuning/overrides/<org>/<cluster>/metric_alert_rules.yml   → merged into cluster-level YAML
```

Both merge by rule name: matching name **replaces** the shipped default; new
name **appends**. Use to correct chart names that differ from the shipped
defaults, fix shipped-default bugs, or retire a rule per-cluster
(`present: false`).

**Put each override in the file matching the level the rule is shipped at.**
Overriding at the wrong level produces a duplicate-name entry that the
shipped rule clobbers when both YAMLs are loaded and concatenated.

### Limit on what overrides can change

The Ansible `alert_rule` module derives each stored `expr` from the
dashboard chart's query template. It honors YAML `operator:` /
`warning_value:` / `critical_value:` / `duration:` / chart-name overrides,
but the `metric:` field is **ignored for the stored expr**. To set a custom
expr you have to bypass the Ansible flow and POST via `apply-tuned-alerts`
(which `tuning/cycle-customer` does when an `EXPR_PATCHER` is configured).

---

## Tuning policy — `cli/exported/tune-alerts-policy.json`

Team-wide pinned thresholds applied automatically by `tuning/tune`. fnmatch
globs against rule names. Each entry should carry a `_why` annotation.

Use the policy file for rules that **aren't workload-tunable**:

- Capacity thresholds (e.g. disk % usage) — these are policy decisions, not
  workload-derived.
- Exception/failure counters that are near-zero on healthy clusters
  (timeouts, unavailables, CAS failures, dropped mutations/reads/hints).
  Computing a p99 from a near-zero series is meaningless; a fixed threshold
  matching the seeded defaults is the right model.
- Queue-depth metrics (pending stages, blocked/pending repair tasks).
- Operational thresholds where crossing them is an operational issue,
  not a tuning one (NTP offset, max partition size).

Validate that a new pattern actually matches the rules you intend:

```python
import fnmatch, json
d = json.load(open('cli/exported/tune-alerts-policy.json'))
rules = json.load(open('cli/exported/<org>/<cluster>/alert_rules.json'))['metricrules']
for p in d['pinned_thresholds']:
    n = sum(1 for r in rules if fnmatch.fnmatchcase(r['alert'], p['pattern']))
    print(f'{p["pattern"]!r} → {n} match(es)')
```

A pattern matching 0 rules is dead — the rule isn't on this cluster, the
name has drifted (manual UI edits add a `(updated X to Y)` suffix), or the
pattern is mistyped.

---

## The label-schema problem

Some AxonOps deployments use different metric label conventions than the
shipped defaults assume. If a cluster encodes consistency into `scope`
(e.g. `scope='Read_LOCAL_ONE'`) and percentile into `function`
(e.g. `function='99thPercentile'`), the shipped rules filter on
`consistency='LOCAL_ONE'` / `percentile='99thPercentile'` — labels that
don't exist on the cluster. Stored exprs match no series; alerts never
fire; the tuner sees 0 samples.

The Ansible `alert_rule` module can't fix this from YAML (chart-template-
derived exprs aren't overridable via the `metric:` field). The workaround:

1. Write a customer-specific `tuning/patch-<name>-broken-exprs` that rewrites
   the affected rules' `expr` fields to use the cluster's actual label
   schema. Each fix is `(corrected_selector, comparison_op)`; the
   threshold comes from the rule's existing `warningValue`.
2. Set `EXPR_PATCHER=patch-<name>-broken-exprs` in the customer's `.env`.
3. `tuning/cycle-customer` runs it as part of every cycle — POST goes through
   `apply-tuned-alerts`, which writes the rule's `expr` field verbatim
   (bypassing the chart-template derivation).

**Verify every corrected selector returns data via a `query_range` probe
before adding it to the patcher.** Don't ship fixes you haven't confirmed.

The proper long-term fix is correcting the dashboard chart query templates
at the source (or, alternatively, the `alert_rule` module's hardcoded
`queries[0]` index — see the `chart_query_index` parameter on the
`feat/alert-rule-chart-query-index` branch).

### Dashboard templates have two parallel storages

The `/api/v1/dashboardtemplate/<org>/<cluster_type>/<cluster>` endpoint
has two versions accessed via the same URL with different query strings:

| URL | Who reads/writes |
|---|---|
| no query string | `alert_rule.py` reads here when deriving the alert's stored expr |
| `?dashver=2.0` | `dashboard_template.py` reads and writes here |

These are independent storages with potentially different content. If you
fix a chart by writing to v2 (`?dashver=2.0`) only and then run
`tuning/default-apply`, the `alert_rule` module reads v1 → sees the old
chart → derives the old expr → reports `changed=0` even though the chart
"looks" fixed in the UI (which reads v2). **Always update both** when
fixing dashboard chart queries.

---

## Reading the tune report

The audit at `cli/exported/<org>/<cluster>/alert_rules.tuned.for.<cluster>.report.md`
categorizes each rule. The **Skipped** section is the interesting one;
each skip reason has a remedy:

| Reason | Cause | Remedy |
|---|---|---|
| `insufficient data (0 samples)` on `cas_ClientRequest_Latency` or `cas_Table_*Histogram` rules | Label schema mismatch (`percentile=` / `consistency=` filters match nothing) | Add an `EXPR_PATCHER` |
| `insufficient data (0 samples)` on rules pinned to a placeholder table | Default rule selectors target the wrong table | `--set-label cas_Table_*:scope=<HOT_TABLE>` (already issued by `tuning/tune-customer`) |
| `insufficient data (N samples)` where N is small but non-zero | Sparse-but-real metric | Increase `DAYS` and/or lower `MIN_SAMPLES` in the customer's `.env` |
| `insufficient data` on CAS failures, dropped mutations, timeouts, queue depths | Exception/failure metrics — near-zero on healthy clusters by design | Pin in `cli/exported/tune-alerts-policy.json` — these aren't workload-tunable |
| `unreasonable delta (max_delta=N)` | Workload-derived threshold > N× the seeded default | Decide whether the seeded threshold is a real operational issue (NTP, partition size — keep seeded) or whether the workload genuinely differs (raise `MAX_DELTA`) |
| `nonsensical (new warning=0.0, ...)` | Computed threshold rounds to 0 (mostly-zero series, or `<=` op on mostly-high values) | Pin to seeded defaults in the policy file |
| `event/log-shape rule (events metric, not workload-tunable)` | `events{…}` selector — log alerts or event-type metric alerts | Correct as-is; these aren't threshold-tunable |
| `query failed: ... returned 500` | `events{}` metric isn't queryable via `query_range` | The tuner pre-filters these as event/log-shape; no action needed |
| `cannot parse expr` (on a rule that isn't event/log-shape) | Stored rule lacks a PromQL trailing threshold | Investigate individually — unusual; usually a manual UI edit |

### Operational thresholds worth surfacing rather than tuning away

Sometimes a rule trips `unreasonable delta` because the workload-derived
value crosses the seeded default by 10×+ — and that crossing is the actual
signal. The seeded defaults encode "this is bad, period" levels for some
metrics:

- **NTP offset** at 5/10 ms — Cassandra timestamp correctness depends on
  <10 ms host clock drift. A median of 100 ms means NTP is misconfigured.
- **Max partition size** at 100 MB / 200 MB — Cassandra best practice.
  A 5 GB partition causes slow reads, repair stalls, and OOMs on streaming.
- **Tombstones scanned** at 500/1000 — the degradation threshold. On a
  healthy table observed values are near 0; tighten to e.g. 50/200 to
  catch growth early.

Before raising `MAX_DELTA` to mask one of these, probe the actual
distribution:

```bash
END=$(date -u +%s); START=$((END - 30*86400))
curl -sS -H "Authorization: Bearer $AXONOPS_TOKEN" \
  --data-urlencode "query=<metric>" \
  --data-urlencode "start=$START" --data-urlencode "end=$END" \
  --data-urlencode "step=1800s" \
  -G "<base-url>/api/v1/query_range" \
| python3 -c "import json,sys,statistics; \
  d=json.loads(sys.stdin.read()); s=d.get('data',{}).get('result') or []; \
  vals=sorted(float(v) for x in s for ts,v in x.get('values') or [] if v==v); \
  print(f'median={vals[len(vals)//2]:.2f} p90={vals[int(len(vals)*0.9)]:.2f} p99={vals[int(len(vals)*0.99)]:.2f} max={vals[-1]:.2f}')"
```

Pick thresholds based on the distribution AND what the metric crossing it
actually means operationally.

---

## Dated export snapshots

Each `tuning/export <org> <cluster>` writes an immutable snapshot dir and
re-points three symlinks:

```
cli/exported/<org>/<cluster>/
├── 2026-05-29T22-38-47Z/         ← this run (immutable)
│   ├── alert_rules.json
│   ├── integrations.json
│   └── .gitignore
├── 2026-05-26T18-49-10Z/         ← previous run, preserved
├── latest            → 2026-05-29T22-38-47Z
├── alert_rules.json  → latest/alert_rules.json
└── integrations.json → latest/integrations.json
```

Downstream tools read the stable `alert_rules.json` and follow the symlink.
Prior exports are never overwritten — timestamps are UTC with second
precision and the script refuses to overwrite an existing snapshot dir.

---

## Notes and gotchas

- **`tuning/default-apply` is destructive — preview with `--check`.** Cycle,
  export, and tune are reconciliation steps; safe to re-run.
- The apply path is **idempotent** — each rule POSTs with its `id` and the
  endpoint upserts. A re-run after a transient failure is safe.
- **Manual UI edits** add a `(updated X to Y)` suffix to the rule name.
  Policy pin patterns are exact matches by default — re-apply via
  `tuning/default-apply` to restore the canonical name + re-pin.
- The Ansible `alert_rule` module's error path **prints the full
  `Authorization` header** (including the token) on failure. Rotate any
  token that appears in an error log.
- The `tune` step skips rules with insufficient data, unreasonable deltas,
  or thresholds that compute to nonsensical values — check the report's
  "Skipped" section before assuming a rule was tuned.
- Percent-shaped metrics are clamped at 100.
- Output dirs are created `0700`; JSON files `0600`.
- `tuning/cycle-customer` exports **before** anything else so manual UI
  changes (rule deletions, edits) are honored; without that first export,
  the apply step would reassert the previous export's state and undo
  whatever you just did in the UI.
- The pre-hook mechanism (`PRE_HOOKS`) is for **idempotent** setup steps
  only. Hooks run with `set -e`; a non-idempotent hook will trip on
  re-runs and stop the cycle before the destructive bits.
