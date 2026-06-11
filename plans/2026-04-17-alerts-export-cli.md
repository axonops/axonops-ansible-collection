# Alerts Export CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `axonopscli alerts --exportpath <dir>` subcommand that exports alert rules and integrations from a single AxonOps SaaS cluster to JSON files, with secret redaction by default. Then fix the pre-existing `cluster_type` bug in `application.py` as a separate trailing commit.

**Architecture:** New `components/alerts.py` containing two classes (`SecretRedactor` for field-name-pattern redaction, `AlertsExporter` for fetch+write+gitignore), wired into `application.py` via a new subparser. Mirrors the existing `dashboard --exportpath` pattern. Trailing commit adds a `--cluster-type` global arg and fixes the hardcoded `/cassandra/` URL fragments in both `dashboard.py` and `alerts.py`.

**Tech Stack:** Python 3.13, `requests` (already a dep), `unittest` + `unittest.mock` for tests. No new dependencies.

**Spec:** `plans/2026-04-17-alerts-export-cli-design.md` (commit 9b99ad5)

**Branch:** `alerts-export-cli` (already created from `main`, design doc already committed)

---

## Pre-flight

- [ ] **Step 0.1: Verify branch and clean state**

```bash
cd /opt/repos/axonops-ansible-collection
git status
git branch --show-current
```

Expected: branch is `alerts-export-cli`, working tree clean (only the design doc committed).

- [ ] **Step 0.2: Verify test runner works on existing tests**

```bash
cd /opt/repos/axonops-ansible-collection/cli
python3 -m unittest discover -s tests -v 2>&1 | tail -5
```

Expected: 9 tests run; 3 pre-existing failures unrelated to our work (`do_login` AttributeError, tuple unpacking in `get_jwt`). New tests we add must pass without depending on those broken paths. Do NOT fix those failures — they are out of scope.

- [ ] **Step 0.3: Re-read the spec**

Read `plans/2026-04-17-alerts-export-cli-design.md` end-to-end to internalize decisions before starting.

---

## Task 1: SecretRedactor helper (Commit 1 of 5)

**Goal:** Pure helper class that walks nested dict/list structures and replaces values whose key matches a known secret pattern with `"***REDACTED***"`. No I/O. Fully unit-testable.

**Files:**

- Create: `cli/axonopscli/components/alerts.py`
- Create: `cli/tests/test_alerts_export_unittest.py`

### Step 1.1: Write the first failing test (Slack webhook)

- [ ] Create `cli/tests/test_alerts_export_unittest.py` with this content:

```python
import unittest

from axonopscli.components.alerts import SecretRedactor, REDACTED


class TestSecretRedactor(unittest.TestCase):

    def test_redacts_slack_webhook_url(self):
        payload = {
            "Type": "slack",
            "Params": {"name": "ops", "webhook_url": "https://hooks.slack.com/services/SECRET"},
        }
        result = SecretRedactor.redact(payload)
        self.assertEqual(result["Params"]["webhook_url"], REDACTED)
        self.assertEqual(result["Params"]["name"], "ops")  # non-secret untouched
        self.assertEqual(result["Type"], "slack")


if __name__ == "__main__":
    unittest.main()
```

### Step 1.2: Run test to verify it fails

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection/cli
python3 -m unittest tests.test_alerts_export_unittest -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'axonopscli.components.alerts'`

### Step 1.3: Create the components/alerts.py file with SecretRedactor

- [ ] Create `cli/axonopscli/components/alerts.py` with this content:

```python
import re

REDACTED = "***REDACTED***"

# Field names whose values are treated as secrets. Match is case-insensitive
# against the full key. To extend: add a regex below. Keep patterns explicit
# (avoid blanket `key`/`token` since those match unrelated fields).
SECRET_FIELD_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r'^webhook_url$',
        r'^api_key$',
        r'^integration_key$',
        r'^service_key$',
        r'^routing_key$',
        r'^auth_token$',
        r'^password$',
        r'^secret$',
    )
]


class SecretRedactor:
    """Recursively redact secret-keyed values in nested dict/list structures.

    Pure function-style; input is not mutated.
    """

    @classmethod
    def redact(cls, obj):
        if isinstance(obj, dict):
            return {
                k: REDACTED if cls._is_secret_key(k) else cls.redact(v)
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [cls.redact(item) for item in obj]
        return obj

    @staticmethod
    def _is_secret_key(key):
        return any(p.match(str(key)) for p in SECRET_FIELD_PATTERNS)
```

### Step 1.4: Run test to verify it passes

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection/cli
python3 -m unittest tests.test_alerts_export_unittest -v
```

Expected: 1 test passes (`test_redacts_slack_webhook_url ... ok`)

### Step 1.5: Add the remaining redactor tests

- [ ] Append to `cli/tests/test_alerts_export_unittest.py` (inside the same `TestSecretRedactor` class), after the existing test method:

```python
    def test_redacts_pagerduty_service_key(self):
        payload = {"Type": "pagerduty", "Params": {"service_key": "abc123"}}
        result = SecretRedactor.redact(payload)
        self.assertEqual(result["Params"]["service_key"], REDACTED)

    def test_redacts_opsgenie_api_key(self):
        payload = {"Type": "opsgenie", "Params": {"api_key": "key-xyz"}}
        result = SecretRedactor.redact(payload)
        self.assertEqual(result["Params"]["api_key"], REDACTED)

    def test_redacts_servicenow_password(self):
        payload = {
            "Type": "servicenow",
            "Params": {"username": "svc", "password": "p@ss", "instance_url": "https://x.service-now.com"},
        }
        result = SecretRedactor.redact(payload)
        self.assertEqual(result["Params"]["password"], REDACTED)
        self.assertEqual(result["Params"]["username"], "svc")  # username intentionally not redacted
        self.assertEqual(result["Params"]["instance_url"], "https://x.service-now.com")  # not in patterns

    def test_redacts_nested_definitions_list_preserves_structure(self):
        payload = {
            "Definitions": [
                {"Type": "slack", "Params": {"webhook_url": "u1"}},
                {"Type": "pagerduty", "Params": {"service_key": "k1"}},
            ],
            "Routing": [{"severity": "error", "integration_name": "ops"}],
        }
        result = SecretRedactor.redact(payload)
        self.assertEqual(result["Definitions"][0]["Params"]["webhook_url"], REDACTED)
        self.assertEqual(result["Definitions"][1]["Params"]["service_key"], REDACTED)
        self.assertEqual(result["Routing"], payload["Routing"])  # untouched
        self.assertEqual(len(result["Definitions"]), 2)

    def test_non_secret_fields_untouched(self):
        payload = {
            "name": "rule1",
            "severity": "warning",
            "duration": "5m",
            "description": "Not a secret",
        }
        result = SecretRedactor.redact(payload)
        self.assertEqual(result, payload)

    def test_input_is_not_mutated(self):
        payload = {"Params": {"webhook_url": "https://example.com"}}
        SecretRedactor.redact(payload)
        self.assertEqual(payload["Params"]["webhook_url"], "https://example.com")
```

### Step 1.6: Run all SecretRedactor tests

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection/cli
python3 -m unittest tests.test_alerts_export_unittest -v
```

Expected: 7 tests pass (1 original + 6 new), 0 failures, 0 errors.

### Step 1.7: Commit

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection
git add cli/axonopscli/components/alerts.py cli/tests/test_alerts_export_unittest.py
git status   # confirm only those two files staged
git commit -m "feat(cli): add SecretRedactor helper for alerts export

Field-name pattern based redaction for nested dict/list structures.
Pure helper, no I/O. Used by the upcoming alerts export subcommand
to redact integration secrets (Slack webhooks, PagerDuty service
keys, Opsgenie API keys, ServiceNow passwords) by default.

The SECRET_FIELD_PATTERNS module-level list is the single source
of truth — easy to extend as AxonOps adds new integration types."
```

---

## Task 2: AlertsExporter — fetch + export + .gitignore (Commit 2 of 5)

**Goal:** Orchestrator class that fetches alert rules and integrations from the API and writes them to JSON files, applying redaction by default and managing a `.gitignore` when secrets are kept.

**Files:**

- Modify: `cli/axonopscli/components/alerts.py` (add `AlertsExporter` class + module constants)
- Modify: `cli/tests/test_alerts_export_unittest.py` (add three new test classes)

### Step 2.1: Write failing test for AlertsExporter.fetch()

- [ ] Append to `cli/tests/test_alerts_export_unittest.py`:

```python
from types import SimpleNamespace
from unittest.mock import patch, MagicMock

from axonopscli.components.alerts import AlertsExporter


def _args(org="acme", cluster="prod", exportpath="/tmp/x", include_secrets=False, v=0):
    return SimpleNamespace(
        org=org, cluster=cluster, exportpath=exportpath,
        include_secrets=include_secrets, v=v,
    )


class TestAlertsExporterFetch(unittest.TestCase):

    def test_fetch_calls_alert_rules_and_integrations_endpoints(self):
        axonops = MagicMock()
        axonops.do_request.side_effect = [
            {"rules": [{"name": "r1"}]},        # alert-rules response
            {"Definitions": [], "Routing": []}, # integrations response
        ]
        args = _args(org="acme", cluster="prod")
        exporter = AlertsExporter(axonops, args)

        exporter.fetch()

        self.assertEqual(axonops.do_request.call_count, 2)
        call_urls = [c.kwargs.get('url') or c.args[0] for c in axonops.do_request.call_args_list]
        self.assertIn("/api/v1/alert-rules/acme/cassandra/prod", call_urls)
        self.assertIn("/api/v1/integrations/acme/cassandra/prod", call_urls)
        self.assertEqual(exporter.alert_rules, {"rules": [{"name": "r1"}]})
        self.assertEqual(exporter.integrations, {"Definitions": [], "Routing": []})

    def test_fetch_normalizes_none_response_to_empty_dict(self):
        axonops = MagicMock()
        axonops.do_request.side_effect = [None, None]
        exporter = AlertsExporter(axonops, _args())

        exporter.fetch()

        self.assertEqual(exporter.alert_rules, {})
        self.assertEqual(exporter.integrations, {})
```

### Step 2.2: Run test to verify it fails

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection/cli
python3 -m unittest tests.test_alerts_export_unittest.TestAlertsExporterFetch -v
```

Expected: FAIL with `ImportError: cannot import name 'AlertsExporter'`

### Step 2.3: Add AlertsExporter skeleton + fetch() to alerts.py

- [ ] Append to `cli/axonopscli/components/alerts.py`:

```python
import json
import os

GITIGNORE_FILENAME = ".gitignore"
SECRETS_WARNING = (
    "WARNING: --include-secrets is set; the export contains live secrets "
    "(webhook URLs, API keys, etc.). File mode is 0600 and the export "
    "directory's .gitignore has been updated to exclude these files."
)


class AlertsExporter:
    """Fetch alert rules and integrations from AxonOps and write them as JSON.

    Single-cluster scope, mirroring `dashboard --exportpath` ergonomics.
    """

    ALERT_RULES_URL = "/api/v1/alert-rules/{org}/cassandra/{cluster}"
    INTEGRATIONS_URL = "/api/v1/integrations/{org}/cassandra/{cluster}"

    def __init__(self, axonops, args):
        self.axonops = axonops
        self.args = args
        self.alert_rules = None
        self.integrations = None

    def fetch(self):
        """Hit both endpoints and store responses. Raises HTTPCodeError on failure."""
        org, cluster = self.args.org, self.args.cluster
        self.alert_rules = self.axonops.do_request(
            url=self.ALERT_RULES_URL.format(org=org, cluster=cluster),
            method='GET',
        ) or {}
        self.integrations = self.axonops.do_request(
            url=self.INTEGRATIONS_URL.format(org=org, cluster=cluster),
            method='GET',
        ) or {}
```

### Step 2.4: Run test to verify it passes

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection/cli
python3 -m unittest tests.test_alerts_export_unittest.TestAlertsExporterFetch -v
```

Expected: 2 tests pass.

### Step 2.5: Write failing tests for AlertsExporter.export()

- [ ] Append to `cli/tests/test_alerts_export_unittest.py`:

```python
import tempfile
import stat


class TestAlertsExporterExport(unittest.TestCase):

    def _make_exporter(self, alert_rules, integrations, exportpath, include_secrets=False):
        exporter = AlertsExporter(MagicMock(), _args(exportpath=exportpath, include_secrets=include_secrets))
        exporter.alert_rules = alert_rules
        exporter.integrations = integrations
        return exporter

    def test_export_writes_both_files_when_both_resources_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = self._make_exporter(
                alert_rules={"rules": [{"name": "r1"}]},
                integrations={"Definitions": [{"Type": "slack", "Params": {"webhook_url": "u"}}],
                              "Routing": [], "Overrides": []},
                exportpath=tmp,
            )
            ex.export(tmp, include_secrets=False)

            self.assertTrue(os.path.exists(os.path.join(tmp, "alert_rules.json")))
            self.assertTrue(os.path.exists(os.path.join(tmp, "integrations.json")))

    def test_export_default_redacts_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = self._make_exporter(
                alert_rules={"rules": [{"name": "r1"}]},
                integrations={"Definitions": [{"Type": "slack", "Params": {"webhook_url": "real-secret"}}],
                              "Routing": [], "Overrides": []},
                exportpath=tmp,
            )
            ex.export(tmp, include_secrets=False)

            with open(os.path.join(tmp, "integrations.json")) as f:
                data = json.load(f)
            self.assertEqual(data["Definitions"][0]["Params"]["webhook_url"], REDACTED)

    def test_export_include_secrets_keeps_real_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = self._make_exporter(
                alert_rules={},
                integrations={"Definitions": [{"Type": "slack", "Params": {"webhook_url": "real-secret"}}],
                              "Routing": [], "Overrides": []},
                exportpath=tmp,
            )
            ex.export(tmp, include_secrets=True)

            with open(os.path.join(tmp, "integrations.json")) as f:
                data = json.load(f)
            self.assertEqual(data["Definitions"][0]["Params"]["webhook_url"], "real-secret")

    def test_export_files_have_mode_0600(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = self._make_exporter(
                alert_rules={"rules": [{"name": "r1"}]},
                integrations={"Definitions": [{"Type": "slack", "Params": {}}]},
                exportpath=tmp,
            )
            ex.export(tmp, include_secrets=False)

            for name in ("alert_rules.json", "integrations.json"):
                mode = stat.S_IMODE(os.stat(os.path.join(tmp, name)).st_mode)
                self.assertEqual(mode, 0o600, f"{name} mode is {oct(mode)}, expected 0o600")

    def test_export_skips_empty_alert_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = self._make_exporter(
                alert_rules={},
                integrations={"Definitions": [{"Type": "slack"}]},
                exportpath=tmp,
            )
            ex.export(tmp, include_secrets=False)

            self.assertFalse(os.path.exists(os.path.join(tmp, "alert_rules.json")))
            self.assertTrue(os.path.exists(os.path.join(tmp, "integrations.json")))

    def test_export_skips_empty_integrations(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = self._make_exporter(
                alert_rules={"rules": [{"name": "r1"}]},
                integrations={"Definitions": [], "Routing": [], "Overrides": []},
                exportpath=tmp,
            )
            ex.export(tmp, include_secrets=False)

            self.assertTrue(os.path.exists(os.path.join(tmp, "alert_rules.json")))
            self.assertFalse(os.path.exists(os.path.join(tmp, "integrations.json")))

    def test_export_writes_nothing_when_both_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = self._make_exporter(alert_rules={}, integrations={}, exportpath=tmp)
            ex.export(tmp, include_secrets=False)

            self.assertEqual(os.listdir(tmp), [])

    def test_export_creates_directory_if_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "new_subdir")
            ex = self._make_exporter(
                alert_rules={"rules": [{"name": "r1"}]},
                integrations={},
                exportpath=target,
            )
            ex.export(target, include_secrets=False)

            self.assertTrue(os.path.isdir(target))
            self.assertTrue(os.path.exists(os.path.join(target, "alert_rules.json")))

    def test_export_raises_when_path_exists_as_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            file_path = os.path.join(tmp, "file_not_dir")
            with open(file_path, 'w') as f:
                f.write("x")
            ex = self._make_exporter(
                alert_rules={"rules": [{"name": "r1"}]},
                integrations={},
                exportpath=file_path,
            )
            with self.assertRaises(NotADirectoryError):
                ex.export(file_path, include_secrets=False)
```

### Step 2.6: Run tests to verify they fail

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection/cli
python3 -m unittest tests.test_alerts_export_unittest.TestAlertsExporterExport -v
```

Expected: All 9 tests FAIL with `AttributeError: 'AlertsExporter' object has no attribute 'export'`

### Step 2.7: Implement AlertsExporter.export() + helpers

- [ ] Append to the `AlertsExporter` class in `cli/axonopscli/components/alerts.py` (inside the class, after `fetch`):

```python
    def export(self, exportpath, include_secrets=False):
        """Write resources to JSON files in exportpath. Returns nothing.

        Behavior:
          - Empty resources are skipped (no file written).
          - Files written with mode 0600.
          - Default: redact secrets via SecretRedactor.
          - With include_secrets=True: keep raw values; ensure exported
            filenames are listed in {exportpath}/.gitignore; print warning.
        """
        if os.path.exists(exportpath) and not os.path.isdir(exportpath):
            raise NotADirectoryError(
                f"Export path '{exportpath}' exists and is not a directory")
        os.makedirs(exportpath, exist_ok=True)

        written = []
        if self._has_alert_rules():
            self._write_resource(exportpath, "alert_rules.json", self.alert_rules, include_secrets)
            written.append("alert_rules.json")
        if self._has_integrations():
            self._write_resource(exportpath, "integrations.json", self.integrations, include_secrets)
            written.append("integrations.json")

        if not written:
            print("No alert rules or integrations found; nothing to export.")
            return

        if include_secrets:
            self._update_gitignore(exportpath, written)
            print(SECRETS_WARNING)

        print(f"Exported {', '.join(written)} to {exportpath}")

    def _has_alert_rules(self):
        return bool(self.alert_rules)

    def _has_integrations(self):
        if not self.integrations:
            return False
        return any(self.integrations.get(s) for s in ("Definitions", "Routing", "Overrides"))

    def _write_resource(self, exportpath, filename, body, include_secrets):
        payload = body if include_secrets else SecretRedactor.redact(body)
        path = os.path.join(exportpath, filename)
        with open(path, "w") as f:
            json.dump(payload, f, indent=4)
        os.chmod(path, 0o600)

    def _update_gitignore(self, exportpath, filenames):
        gitignore_path = os.path.join(exportpath, GITIGNORE_FILENAME)
        existing_lines = []
        if os.path.exists(gitignore_path):
            with open(gitignore_path, "r") as f:
                existing_lines = [line.rstrip("\n") for line in f.readlines()]
        existing_set = {line.strip() for line in existing_lines if line.strip()}
        to_add = [name for name in filenames if name not in existing_set]
        if not to_add:
            return
        with open(gitignore_path, "w") as f:
            for line in existing_lines:
                f.write(line + "\n")
            for name in to_add:
                f.write(name + "\n")
```

### Step 2.8: Run export tests to verify they pass

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection/cli
python3 -m unittest tests.test_alerts_export_unittest.TestAlertsExporterExport -v
```

Expected: 9 tests pass.

### Step 2.9: Write failing tests for .gitignore management

- [ ] Append to `cli/tests/test_alerts_export_unittest.py`:

```python
class TestAlertsExporterGitignore(unittest.TestCase):

    def _exporter_with_full_data(self, exportpath, include_secrets):
        ex = AlertsExporter(MagicMock(), _args(exportpath=exportpath, include_secrets=include_secrets))
        ex.alert_rules = {"rules": [{"name": "r1"}]}
        ex.integrations = {"Definitions": [{"Type": "slack", "Params": {"webhook_url": "u"}}],
                           "Routing": [], "Overrides": []}
        return ex

    def test_gitignore_created_with_both_filenames_when_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = self._exporter_with_full_data(tmp, include_secrets=True)
            ex.export(tmp, include_secrets=True)

            gitignore_path = os.path.join(tmp, ".gitignore")
            self.assertTrue(os.path.exists(gitignore_path))
            with open(gitignore_path) as f:
                lines = [line.strip() for line in f if line.strip()]
            self.assertIn("alert_rules.json", lines)
            self.assertIn("integrations.json", lines)

    def test_gitignore_appends_only_missing_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            gitignore_path = os.path.join(tmp, ".gitignore")
            with open(gitignore_path, "w") as f:
                f.write("alert_rules.json\n*.tmp\n")  # already has alert_rules.json
            ex = self._exporter_with_full_data(tmp, include_secrets=True)
            ex.export(tmp, include_secrets=True)

            with open(gitignore_path) as f:
                lines = [line.strip() for line in f if line.strip()]
            self.assertEqual(lines.count("alert_rules.json"), 1)  # no duplicate
            self.assertIn("integrations.json", lines)
            self.assertIn("*.tmp", lines)  # original entries preserved

    def test_gitignore_unchanged_when_both_already_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            gitignore_path = os.path.join(tmp, ".gitignore")
            original = "alert_rules.json\nintegrations.json\n"
            with open(gitignore_path, "w") as f:
                f.write(original)
            ex = self._exporter_with_full_data(tmp, include_secrets=True)
            ex.export(tmp, include_secrets=True)

            with open(gitignore_path) as f:
                self.assertEqual(f.read(), original)

    def test_gitignore_not_written_when_secrets_redacted(self):
        with tempfile.TemporaryDirectory() as tmp:
            ex = self._exporter_with_full_data(tmp, include_secrets=False)
            ex.export(tmp, include_secrets=False)

            self.assertFalse(os.path.exists(os.path.join(tmp, ".gitignore")))
```

### Step 2.10: Run gitignore tests to verify they pass

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection/cli
python3 -m unittest tests.test_alerts_export_unittest.TestAlertsExporterGitignore -v
```

Expected: 4 tests pass. (They should pass because the implementation in Step 2.7 already covers this behavior.)

### Step 2.11: Run all alerts tests together

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection/cli
python3 -m unittest tests.test_alerts_export_unittest -v
```

Expected: 7 + 2 + 9 + 4 = 22 tests pass, 0 failures, 0 errors.

### Step 2.12: Commit

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection
git add cli/axonopscli/components/alerts.py cli/tests/test_alerts_export_unittest.py
git status   # confirm only those two files staged
git commit -m "feat(cli): add AlertsExporter with fetch and export

AlertsExporter orchestrates GETs to /api/v1/alert-rules and
/api/v1/integrations, applies SecretRedactor by default, and writes
JSON files (mode 0600) to the export path. Empty resources are
skipped entirely.

When --include-secrets is used, the exported filenames are
auto-appended to a .gitignore in the export directory as defense
in depth against accidental git commits. Existing .gitignore
contents are preserved; duplicates are not introduced.

URLs hardcode 'cassandra' for the cluster type; this is consistent
with the dashboard component and is corrected by the trailing
cluster_type fix commit on this branch."
```

---

## Task 3: Wire `alerts` subcommand into application.py (Commit 3 of 5)

**Goal:** Make `axonopscli alerts --exportpath ...` invocable from the CLI. Add an end-to-end test that exercises `application.run()`.

**Files:**

- Modify: `cli/axonopscli/application.py:163-209` (insert new subparser block after `silence_parser` and before `parsed_result = parser.parse_args(...)`); add `run_alerts` method
- Modify: `cli/tests/test_alerts_export_unittest.py` (add end-to-end test class)

### Step 3.1: Write failing end-to-end test

- [ ] Append to `cli/tests/test_alerts_export_unittest.py`:

```python
class TestApplicationRunAlerts(unittest.TestCase):

    def _patch_axonops(self, alert_rules_response, integrations_response):
        """Patch AxonOps.do_request at the class level to return canned responses."""
        from axonopscli.axonops import AxonOps

        responses = {
            "/api/v1/alert-rules/acme/cassandra/prod": alert_rules_response,
            "/api/v1/integrations/acme/cassandra/prod": integrations_response,
        }

        def fake_do_request(self, url, method='GET', **kwargs):
            return responses.get(url, {})

        return patch.object(AxonOps, 'do_request', new=fake_do_request)

    def test_application_run_alerts_writes_files(self):
        from axonopscli.application import Application

        with tempfile.TemporaryDirectory() as tmp:
            with self._patch_axonops(
                alert_rules_response={"rules": [{"name": "r1"}]},
                integrations_response={"Definitions": [{"Type": "slack", "Params": {"webhook_url": "u"}}],
                                       "Routing": [], "Overrides": []},
            ):
                app = Application()
                app.run([
                    "--org", "acme",
                    "--cluster", "prod",
                    "--token", "t",
                    "alerts",
                    "--exportpath", tmp,
                ])

            self.assertTrue(os.path.exists(os.path.join(tmp, "alert_rules.json")))
            self.assertTrue(os.path.exists(os.path.join(tmp, "integrations.json")))

            with open(os.path.join(tmp, "integrations.json")) as f:
                data = json.load(f)
            self.assertEqual(data["Definitions"][0]["Params"]["webhook_url"], REDACTED)

    def test_application_run_alerts_with_include_secrets(self):
        from axonopscli.application import Application

        with tempfile.TemporaryDirectory() as tmp:
            with self._patch_axonops(
                alert_rules_response={},
                integrations_response={"Definitions": [{"Type": "slack", "Params": {"webhook_url": "u"}}],
                                       "Routing": [], "Overrides": []},
            ):
                app = Application()
                app.run([
                    "--org", "acme",
                    "--cluster", "prod",
                    "--token", "t",
                    "alerts",
                    "--exportpath", tmp,
                    "--include-secrets",
                ])

            with open(os.path.join(tmp, "integrations.json")) as f:
                data = json.load(f)
            self.assertEqual(data["Definitions"][0]["Params"]["webhook_url"], "u")

            with open(os.path.join(tmp, ".gitignore")) as f:
                gi_lines = {line.strip() for line in f if line.strip()}
            self.assertIn("integrations.json", gi_lines)
```

### Step 3.2: Run test to verify it fails

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection/cli
python3 -m unittest tests.test_alerts_export_unittest.TestApplicationRunAlerts -v
```

Expected: FAIL with argparse error or `SystemExit` because the `alerts` subcommand doesn't exist yet.

### Step 3.3: Add the alerts subparser block in application.py

- [ ] Open `cli/axonopscli/application.py`. Find the line `parsed_result: argparse.Namespace = parser.parse_args(args=argv)` (around line 211). Immediately above that line — right after the `silence_parser.add_argument('--silencescheduledreportsalerts', ...)` block — insert:

```python
        alerts_parser = commands_subparser.add_parser(
            "alerts",
            help="Export AxonOps alert rules, routes, and integrations to JSON")

        alerts_parser.set_defaults(func=self.run_alerts)

        alerts_parser.add_argument('--exportpath', type=str, required=True,
                                   help='Directory to write alert rules and integrations '
                                        'JSON files. Created if missing.')
        alerts_parser.add_argument('--include-secrets', action='store_true', default=False,
                                   help='Include integration secrets (webhook URLs, API '
                                        'keys, etc.) in the export instead of redacting. '
                                        'When set, exported filenames are auto-appended '
                                        'to a .gitignore in the export directory.')
```

### Step 3.4: Add the run_alerts method

- [ ] In the same file, append a new method to the `Application` class (after `run_silence`):

```python
    def run_alerts(self, args: argparse.Namespace):
        """ Run the alerts export """
        if args.v:
            print(f"Running alerts export on {args.org}/{args.cluster}")
            print(args)

        axonops = self.get_axonops(args)

        from .components.alerts import AlertsExporter
        exporter = AlertsExporter(axonops, args)
        exporter.fetch()
        exporter.export(args.exportpath, include_secrets=args.include_secrets)
```

### Step 3.5: Run end-to-end tests to verify they pass

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection/cli
python3 -m unittest tests.test_alerts_export_unittest.TestApplicationRunAlerts -v
```

Expected: 2 tests pass.

### Step 3.6: Run the entire alerts test module to verify nothing regressed

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection/cli
python3 -m unittest tests.test_alerts_export_unittest -v
```

Expected: 22 + 2 = 24 tests pass.

### Step 3.7: Smoke test the CLI help output

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection/cli
python3 -c "from axonopscli.application import Application; Application().run(['alerts', '--help'])" 2>&1 | head -25
```

Expected: argparse help showing `--exportpath` (required) and `--include-secrets` (flag).

### Step 3.8: Commit

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection
git add cli/axonopscli/application.py cli/tests/test_alerts_export_unittest.py
git status   # confirm only those two files staged
git commit -m "feat(cli): wire alerts export subcommand into application.py

Adds the 'alerts' subparser and run_alerts handler so users can
invoke:

  axonopscli --org X --cluster Y --token Z alerts \\
      --exportpath ./backup [--include-secrets]

End-to-end tests patch AxonOps.do_request at the class level and
exercise both default-redacted and --include-secrets paths,
verifying the .gitignore is created in the latter case."
```

---

## Task 4: Documentation (Commit 4 of 5)

**Goal:** Document the new subcommand in the CLI README so it's discoverable.

**Files:**

- Modify: `cli/README.md` (append a new section after the existing usage examples)

### Step 4.1: Find the right insertion point in cli/README.md

- [ ] Read `cli/README.md` to locate the section listing existing subcommands (`dashboard`, `silence`, `repair`, etc.). The new `alerts` section should sit alongside them in the same style.

```bash
cat /opt/repos/axonops-ansible-collection/cli/README.md | head -200
```

### Step 4.2: Add the alerts section to cli/README.md

- [ ] Append the following section to `cli/README.md`. If the README has a "Commands" or "Subcommands" heading and other commands are listed under it, place this section there in alphabetical order (it sorts before `dashboard`). Otherwise, append at the end of the file.

```markdown
### `alerts` — Export alert rules and integrations

Export configured alert rules and integrations from a single AxonOps cluster
to JSON files. Mirrors the ergonomics of `dashboard --exportpath`.

**Usage:**

```shell
axonopscli --org $AXONOPS_ORG --cluster $AXONOPS_CLUSTER --token $AXONOPS_TOKEN \
    alerts --exportpath ./backup
```

**Output:** writes `alert_rules.json` and `integrations.json` (each mode 0600)
into the export directory. Empty resources are skipped — if the cluster has
no alert rules, no `alert_rules.json` is written.

**Secret handling:** by default, secret-bearing fields in integration
definitions (`webhook_url`, `api_key`, `service_key`, `integration_key`,
`routing_key`, `auth_token`, `password`, `secret`) are replaced with
`***REDACTED***`. To export raw values (e.g. for restore to another instance),
pass `--include-secrets`. When set, the CLI auto-appends the exported
filenames to a `.gitignore` in the export directory as defense in depth
against accidentally committing secrets.

**Flags:**

| Flag | Required | Description |
|------|----------|-------------|
| `--exportpath PATH` | yes | Directory to write JSON files (created if missing). |
| `--include-secrets` | no | Keep secret values in the export. Default: redacted. |
```

### Step 4.3: Verify the markdown renders correctly

- [ ] Run:

```bash
cat /opt/repos/axonops-ansible-collection/cli/README.md | tail -40
```

Confirm the new section reads cleanly and code fences are properly closed.

### Step 4.4: Commit

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection
git add cli/README.md
git status   # confirm only README staged
git commit -m "docs(cli): document alerts export subcommand

Add a section to cli/README.md describing 'axonopscli alerts
--exportpath', the default-redacted secret behavior, and the
.gitignore safety net activated by --include-secrets."
```

---

## Task 5: Fix `cluster_type` bug (Commit 5 of 5)

**Goal:** Fix the pre-existing bug at `application.py:32` where `cluster_type=args.cluster` (the cluster *name*) is wrongly passed as the cluster *type*. Add a new global `--cluster-type` arg defaulting to `"cassandra"`. Update `dashboard.py` and the new `alerts.py` to use `axonops.get_cluster_type()` instead of hardcoded `"cassandra"` in URLs.

**Files:**

- Modify: `cli/axonopscli/application.py:32, ~50` (add `--cluster-type` arg; pass it correctly to AxonOps)
- Modify: `cli/axonopscli/components/dashboard.py:10` (use `axonops.get_cluster_type()` in URL)
- Modify: `cli/axonopscli/components/alerts.py` (parameterize `cluster_type` in `ALERT_RULES_URL`/`INTEGRATIONS_URL` and fill from `axonops.get_cluster_type()`)
- Modify: `cli/tests/test_alerts_export_unittest.py` (no changes — `_args()` factory must add `cluster_type="cassandra"` so end-to-end tests still pass)

### Step 5.1: Write a failing test for the new `--cluster-type` flag

- [ ] Append to `cli/tests/test_alerts_export_unittest.py`:

```python
class TestClusterTypeFix(unittest.TestCase):

    def test_application_passes_cluster_type_default_cassandra(self):
        from axonopscli.axonops import AxonOps
        from axonopscli.application import Application

        captured = {}
        original_init = AxonOps.__init__

        def capturing_init(self, *args, **kwargs):
            captured['cluster_type'] = kwargs.get('cluster_type')
            original_init(self, *args, **kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(AxonOps, '__init__', new=capturing_init), \
                 patch.object(AxonOps, 'do_request', return_value={}):
                Application().run([
                    "--org", "acme", "--cluster", "prod", "--token", "t",
                    "alerts", "--exportpath", tmp,
                ])

        self.assertEqual(captured['cluster_type'], 'cassandra')

    def test_application_passes_cluster_type_when_overridden(self):
        from axonopscli.axonops import AxonOps
        from axonopscli.application import Application

        captured = {}
        original_init = AxonOps.__init__

        def capturing_init(self, *args, **kwargs):
            captured['cluster_type'] = kwargs.get('cluster_type')
            original_init(self, *args, **kwargs)

        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(AxonOps, '__init__', new=capturing_init), \
                 patch.object(AxonOps, 'do_request', return_value={}):
                Application().run([
                    "--org", "acme", "--cluster", "prod", "--cluster-type", "kafka",
                    "--token", "t",
                    "alerts", "--exportpath", tmp,
                ])

        self.assertEqual(captured['cluster_type'], 'kafka')
```

### Step 5.2: Run test to verify it fails

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection/cli
python3 -m unittest tests.test_alerts_export_unittest.TestClusterTypeFix -v
```

Expected: FAIL — first test fails because `cluster_type='prod'` (the cluster name) instead of `'cassandra'`; second test fails on argparse because `--cluster-type` doesn't exist.

### Step 5.3: Add `--cluster-type` argument to the global parser in application.py

- [ ] Open `cli/axonopscli/application.py`. Find the line near `--cluster` argument (around line 42–43). Right after the `--cluster` argument block, add:

```python
        parser.add_argument('--cluster-type', type=str, required=False,
                            default=os.getenv('AXONOPS_CLUSTER_TYPE', 'cassandra'),
                            help='Cluster type (e.g. cassandra, kafka). Defaults to cassandra.')
```

### Step 5.4: Fix `cluster_type` value passed to AxonOps

- [ ] Open `cli/axonopscli/application.py`. Find the `get_axonops` method (around line 25). Change:

```python
            self.axonops = AxonOps(args.org,
                                   api_token=args.token,
                                   base_url=args.url,
                                   username=args.username,
                                   password=args.password,
                                   cluster_type=args.cluster,
                                   verbose=args.v)
```

to:

```python
            self.axonops = AxonOps(args.org,
                                   api_token=args.token,
                                   base_url=args.url,
                                   username=args.username,
                                   password=args.password,
                                   cluster_type=args.cluster_type,
                                   verbose=args.v)
```

The single-line change: `cluster_type=args.cluster` → `cluster_type=args.cluster_type`.

### Step 5.5: Update dashboard.py to use get_cluster_type()

- [ ] Open `cli/axonopscli/components/dashboard.py`. Find the line:

```python
        self.full_dashboard_url = f"{self.dashboardtemplate_url}/{args.org}/cassandra/{args.cluster}?dashver=2.0"
```

Change to:

```python
        self.full_dashboard_url = f"{self.dashboardtemplate_url}/{args.org}/{axonops.get_cluster_type()}/{args.cluster}?dashver=2.0"
```

### Step 5.6: Update alerts.py to use parameterized cluster_type

- [ ] Open `cli/axonopscli/components/alerts.py`. Find the URL constants:

```python
    ALERT_RULES_URL = "/api/v1/alert-rules/{org}/cassandra/{cluster}"
    INTEGRATIONS_URL = "/api/v1/integrations/{org}/cassandra/{cluster}"
```

Change to:

```python
    ALERT_RULES_URL = "/api/v1/alert-rules/{org}/{cluster_type}/{cluster}"
    INTEGRATIONS_URL = "/api/v1/integrations/{org}/{cluster_type}/{cluster}"
```

Then update the `fetch()` method to pass `cluster_type`:

```python
    def fetch(self):
        """Hit both endpoints and store responses. Raises HTTPCodeError on failure."""
        org, cluster = self.args.org, self.args.cluster
        cluster_type = self.axonops.get_cluster_type()
        self.alert_rules = self.axonops.do_request(
            url=self.ALERT_RULES_URL.format(org=org, cluster_type=cluster_type, cluster=cluster),
            method='GET',
        ) or {}
        self.integrations = self.axonops.do_request(
            url=self.INTEGRATIONS_URL.format(org=org, cluster_type=cluster_type, cluster=cluster),
            method='GET',
        ) or {}
```

### Step 5.7: Update the existing `_args()` test factory and fetch test URL assertions

- [ ] Open `cli/tests/test_alerts_export_unittest.py`. The fetch tests assert URL contents like `/api/v1/alert-rules/acme/cassandra/prod`. After the fix, the URL is built by interpolating `axonops.get_cluster_type()`, which the `MagicMock()` axonops returns as a `Mock` object — breaking the URL.

    Update the `TestAlertsExporterFetch` setup so the mock returns `"cassandra"` for `get_cluster_type()`:

```python
    def test_fetch_calls_alert_rules_and_integrations_endpoints(self):
        axonops = MagicMock()
        axonops.get_cluster_type.return_value = "cassandra"   # <-- ADD
        axonops.do_request.side_effect = [
            {"rules": [{"name": "r1"}]},
            {"Definitions": [], "Routing": []},
        ]
        # ... rest unchanged
```

Add the same `axonops.get_cluster_type.return_value = "cassandra"` line to:

- `test_fetch_normalizes_none_response_to_empty_dict`

The `_make_exporter` and `_exporter_with_full_data` helpers in `TestAlertsExporterExport` and `TestAlertsExporterGitignore` do NOT need updating — those tests bypass `fetch()` and never invoke `get_cluster_type()`.

### Step 5.8: Run all alerts tests to verify they all pass

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection/cli
python3 -m unittest tests.test_alerts_export_unittest -v
```

Expected: 24 + 2 (cluster type) = 26 tests pass, 0 failures, 0 errors.

### Step 5.9: Run the entire CLI test suite to verify no regressions

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection/cli
python3 -m unittest discover -s tests -v 2>&1 | tail -10
```

Expected: All tests pass except the 3 pre-existing failures (`do_login` / `get_jwt` tuple unpacking) noted in Step 0.2. Do NOT fix those — out of scope.

### Step 5.10: Commit

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection
git add cli/axonopscli/application.py cli/axonopscli/components/dashboard.py cli/axonopscli/components/alerts.py cli/tests/test_alerts_export_unittest.py
git status   # confirm only those four files staged
git commit -m "fix(cli): pass cluster_type correctly to AxonOps

application.py was passing args.cluster (the cluster *name*) as
the cluster_type argument to AxonOps, which caused get_cluster_type()
to return the cluster name instead of 'cassandra'/'kafka'. The
existing dashboard component worked around this by hardcoding
'cassandra' in its URL.

Adds a global --cluster-type flag (default 'cassandra', env
AXONOPS_CLUSTER_TYPE) and passes it through correctly. Updates
dashboard.py and alerts.py to interpolate axonops.get_cluster_type()
in URLs instead of hardcoding the string.

This is a behavior change for users who relied on the bugged
behavior: previously, get_cluster_type() returned the cluster name;
now it returns 'cassandra' by default. URLs still hit the correct
endpoints because the previous URL templates also hardcoded
'cassandra'."
```

---

## Final verification

### Step F.1: Full test suite

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection/cli
python3 -m unittest discover -s tests -v 2>&1 | tail -15
```

Expected: 26 new tests pass + 6 of 9 pre-existing tests pass; 3 pre-existing failures unchanged.

### Step F.2: Commit history check

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection
git log --oneline main..HEAD
```

Expected output (top to bottom = newest to oldest):

```
<sha> fix(cli): pass cluster_type correctly to AxonOps
<sha> docs(cli): document alerts export subcommand
<sha> feat(cli): wire alerts export subcommand into application.py
<sha> feat(cli): add AlertsExporter with fetch and export
<sha> feat(cli): add SecretRedactor helper for alerts export
<sha> docs(plans): design for alerts export CLI subcommand
```

Six commits total (one design doc + five implementation commits).

### Step F.3: Smoke test the CLI end-to-end (no live API)

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection/cli
python3 -c "from axonopscli.application import Application; Application().run(['alerts', '--help'])"
```

Expected: argparse help output for the `alerts` subcommand listing `--exportpath` and `--include-secrets`.

### Step F.4: Self-review the diff

- [ ] Run:

```bash
cd /opt/repos/axonops-ansible-collection
git diff main..HEAD --stat
```

Expected: ~5 files changed, roughly 400–500 insertions across components/alerts.py, tests, application.py, dashboard.py edit, README.

- [ ] Hand control back to the engineering manager (the calling agent). Do NOT run `/review`, `/code-review:code-review`, `/pr-review-toolkit:review-pr`, `/code-simplifier`, or `/security-review` — those are the manager's responsibility per PROMPT.ORG.

---

## Notes for the implementing engineer

- **DRY:** Before adding any helper, search `cli/axonopscli/` for an existing utility. The redactor and exporter are both new because nothing equivalent exists; do not duplicate this logic elsewhere.
- **YAGNI:** No re-import, no multi-cluster, no filtering, no encryption, no support for non-Cassandra clusters beyond the `--cluster-type` flag plumbing. Stop scope-creep at the door.
- **TDD:** Every implementation step must have its test written and failing first. Do not implement without seeing the failure.
- **No `--no-verify`, no `--no-gpg-sign`:** Signing was disabled at repo level by the user. Do not touch that config.
- **One commit per task:** Do not squash. Do not amend prior commits.
- **If a step fails unexpectedly:** Stop. Report back to the calling agent (engineering manager) with full context. Do not invent fixes.
- **Pre-existing test failures (`do_login`, `get_jwt`):** Out of scope. Do not touch.
