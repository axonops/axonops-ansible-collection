# Design: `axonopscli alerts --exportpath`

**Date:** 2026-04-17
**Status:** Approved (pending spec review)
**Repo:** `axonops-ansible-collection`
**Scope:** Add a CLI subcommand to export configured alert rules, alert routes, and integrations from a single AxonOps SaaS cluster to JSON files. Fix the `cluster_type` arg bug as a follow-up commit in the same branch.

## Problem

The collection has no way to dump existing alert configuration out of an AxonOps organization. Modules read state only to decide whether to PUT/POST/DELETE; they never expose it. The CLI has `dashboard --exportpath` but no equivalent for alerts. Users who want to back up, inspect, or replicate an org's alerting setup currently have to call the REST API by hand.

## Goal

A new `axonopscli alerts --exportpath ./dir` subcommand that writes alert rules and integration configuration to JSON files in `./dir`, mirroring the ergonomics of the existing `dashboard --exportpath` command.

## Non-goals

- Re-import (`alerts --importpath`)
- Multi-cluster / org-wide loop (single cluster per invocation, like `dashboard --exportpath`)
- Filter by rule name
- New self-hosted-specific auth handling (existing `--url` already covers it)
- Exporting silences, dashboards, service checks, backups (separate resources, separate scope)

## Decisions and rationale

| Decision | Choice | Why |
|---|---|---|
| Scope per invocation | Single cluster, requires `--cluster` | Matches existing `dashboard --exportpath` pattern. Loops are the user's job. |
| File layout | One JSON file per resource group: `alert_rules.json`, `integrations.json` | Maps 1:1 to API responses. Simplest, restorable later by POSTing back. |
| Secret handling | Redact by default, opt-in `--include-secrets` | Safe by default. Backup files end up on disk and in tarballs; field-level redaction prevents accidental exfiltration. |
| Redaction strategy | Field-name pattern matching | Robust to new integration types added by AxonOps without code changes. Fields list is a module-level constant — easy to review/extend. |
| Empty-resource behavior | Skip writing the file entirely | Per user direction: empty files are noise. Caller can detect missing files. |
| `--include-secrets` safety net | Ensure exported files are listed in `.gitignore` in the export dir | Defense in depth: even with file mode 0600, the most likely accidental exfiltration is `git add` in a parent repo. The CLI proactively prevents that. |
| `cluster_type` bug | Fix in a separate trailing commit | Pre-existing bug in `application.py:32`. Per PROMPT.ORG: not bundled into the feature. Surfaced and fixed in its own commit at the end of the same branch. |

## Architecture

```
cli/axonopscli/
├── application.py              [modified — add subparser + run_alerts method]
├── components/
│   └── alerts.py               [new — ~120 lines]
└── ...

cli/tests/
└── test_alerts_export_unittest.py    [new — ~150 lines]
```

No changes to `plugins/module_utils/`. No new runtime dependencies.

### `components/alerts.py`

Two classes in one file (kept together — they share state and lifecycle):

**`SecretRedactor`** — pure helper, zero I/O.

- Module-level constant `SECRET_FIELD_PATTERNS` (list of compiled regexes against field name): `webhook_url`, `key`, `api_key`, `integration_key`, `service_key`, `routing_key`, `token`, `auth_token`, `password`, `secret`, `auth`.
- Single method: `redact(obj)` — recursively walks dicts/lists, returns a new structure with secret-keyed values replaced by `"***REDACTED***"`. Non-string scalars under secret keys are also replaced.
- The `url` key is intentionally NOT in the patterns — too broad. `webhook_url` and `service_url` patterns cover the common cases.
- Pure / immutable: input is not mutated.

**`AlertsExporter`** — orchestrator.

```python
class AlertsExporter:
    ALERT_RULES_URL  = "/api/v1/alert-rules/{org}/cassandra/{cluster}"
    INTEGRATIONS_URL = "/api/v1/integrations/{org}/cassandra/{cluster}"

    def __init__(self, axonops, args):
        self.axonops = axonops
        self.args = args
        self.alert_rules = None
        self.integrations = None

    def fetch(self):
        """Hit both endpoints. Raises on HTTP error. Stores responses."""

    def export(self, exportpath, include_secrets=False):
        """
        Ensure exportpath dir exists. For each non-empty resource:
          - apply redaction if not include_secrets
          - write {exportpath}/{name}.json with mode 0600
        If include_secrets is True and any file was written, ensure the
        written filenames are listed in {exportpath}/.gitignore (append
        if .gitignore exists, create with mode 0644 otherwise; never
        duplicate existing entries).
        Print a one-line summary of what was written and what was skipped.
        Print a warning when include_secrets is True.
        """
```

`cassandra` is hardcoded in URL templates pre-fix; replaced with `self.axonops.get_cluster_type()` in the trailing fix commit.

### `application.py` changes

Add a subparser block after `silence_parser`:

```python
alerts_parser = commands_subparser.add_parser(
    "alerts",
    help="Export alert rules, routes, and integrations from AxonOps")
alerts_parser.set_defaults(func=self.run_alerts)
alerts_parser.add_argument('--exportpath', type=str, required=True,
                           help='Directory to write alert rules and integrations JSON files')
alerts_parser.add_argument('--include-secrets', action='store_true', default=False,
                           help='Include integration secrets (webhook URLs, API keys, etc.) '
                                'in the export. Default: redacted.')
```

And a corresponding `run_alerts` method that constructs `AlertsExporter`, calls `fetch()`, then `export()`.

## Data flow

```
$ axonopscli --org acme --cluster prod alerts --exportpath ./backup
        │
        ├── AxonOps(org='acme', api_token=..., cluster_type='prod')   ← bug; behaves OK because URLs hardcode 'cassandra'
        │
        ├── AlertsExporter.fetch()
        │     ├── GET /api/v1/alert-rules/acme/cassandra/prod   → metric+log rules
        │     └── GET /api/v1/integrations/acme/cassandra/prod  → Definitions + Routing + Overrides
        │
        ├── AlertsExporter.export('./backup', include_secrets=False)
        │     ├── (if alert_rules non-empty)
        │     │     SecretRedactor.redact(alert_rules)  ← rules don't usually contain secrets, but redact anyway for safety
        │     │     write ./backup/alert_rules.json    [0600]
        │     ├── (if integrations non-empty)
        │     │     SecretRedactor.redact(integrations)
        │     │     write ./backup/integrations.json   [0600]
        │     ├── (only if include_secrets and any file was written)
        │     │     ensure ./backup/.gitignore lists the written filenames
        │     │     print warning about sensitive content on disk
        │     └── print summary
        │
        └── exit 0
```

"Non-empty" means: for `alert_rules`, the response has at least one rule; for `integrations`, at least one of Definitions, Routing, or Overrides has entries.

## Error handling

- HTTP/auth failures from `do_request` → print error to stderr, exit non-zero. Match `dashboard` component style.
- `--exportpath` exists as a regular file → error and exit non-zero.
- `--exportpath` doesn't exist → create it (mkdir -p semantics).
- Unwritable directory → error and exit non-zero.
- Empty alert_rules and empty integrations → print a one-line "nothing to export" message, exit 0. Don't write files.

## Testing strategy

Standard `unittest` + `unittest.mock`, matching existing `cli/tests/` patterns. No live API calls.

`cli/tests/test_alerts_export_unittest.py`:

1. **`SecretRedactor` unit tests** (~6 cases)
    - Slack integration with `webhook_url` → redacted
    - PagerDuty with `service_key` → redacted
    - Opsgenie with `api_key` → redacted
    - ServiceNow with `password` → redacted
    - Nested integration list inside `Definitions` → all redacted, structure preserved
    - Non-secret fields (`name`, `type`, `severity`) → untouched

2. **`AlertsExporter.fetch()`** (~3 cases)
    - Happy path: assert correct URLs called, responses stored
    - HTTP error from alert-rules endpoint: error propagates
    - HTTP error from integrations endpoint: error propagates

3. **`AlertsExporter.export()`** (~6 cases)
    - Both resources present, default redaction → two files written, secrets redacted, mode 0600
    - Both resources present, `--include-secrets` → secrets preserved
    - Empty alert_rules → only `integrations.json` written
    - Empty integrations → only `alert_rules.json` written
    - Both empty → no files written, summary printed
    - `exportpath` is a file → raises / errors

4. **`.gitignore` management** (~4 cases)
    - `--include-secrets`, no existing `.gitignore` → file created with both filenames, mode 0644
    - `--include-secrets`, existing `.gitignore` already lists one filename → only the missing one appended; no duplicates
    - `--include-secrets`, existing `.gitignore` lists both → file unchanged
    - default (redacted) export → no `.gitignore` written or modified

5. **End-to-end through `application.run`** (~2 cases)
    - Patch `AxonOps.do_request` at the class level, run `['alerts', '--exportpath', tmpdir]`
    - Same with `--include-secrets`

Total: ~21 test cases, ~180 lines including fixtures.

## Commit breakdown

Atomic commits, each independently revertible:

1. `feat(cli): add SecretRedactor helper` — `components/alerts.py` with just the redactor class + its unit tests
2. `feat(cli): add AlertsExporter (fetch + export)` — main exporter logic, no CLI wiring yet, plus its unit tests
3. `feat(cli): wire alerts subcommand into application.py` — argparse + `run_alerts` + end-to-end tests
4. `docs(cli): document alerts export subcommand` — README/docs update
5. `fix(cli): pass cluster_type correctly to AxonOps` — adds `--cluster-type` arg defaulting to `cassandra`, threads through `application.py`, removes hardcoded `cassandra` from `dashboard.py` and `alerts.py`, updates affected tests

## Out of scope (acknowledged, deferred)

- Re-import of the exported JSON
- Multi-cluster / org-wide export
- Filtering (by rule name, by integration type)
- Exporting silences, dashboards, service checks, backups, adaptive repair config
- Encryption of the export file (caller's responsibility — file mode 0600 is the only at-rest protection)

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| New AxonOps integration type uses a secret field name not in our patterns list | Medium | Pattern list is module-level constant, easy to extend. Document in `alerts.py`. |
| Redaction misses something subtle (e.g. secret embedded in a free-text description) | Low | Out of scope for field-name redaction. Document the limitation. |
| `cluster_type` fix breaks existing dashboard tests | Low | Fix commit updates dashboard tests in lockstep. Reviewed independently. |
| User runs export with `--include-secrets` and commits the file to git | User error → defense in depth | (a) Print a warning when `--include-secrets` is set. (b) Auto-append exported filenames to `{exportpath}/.gitignore`. (c) Document in `--help`. |

## Open questions

None. All Q&A resolved during brainstorming.
