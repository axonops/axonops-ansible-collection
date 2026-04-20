import json
import os
import re

from axonopscli.api import ALERT_RULES_URL, INTEGRATIONS_URL

REDACTED = "***REDACTED***"
GITIGNORE_FILENAME = ".gitignore"
SECRETS_WARNING = (
    "WARNING: --include-secrets is set; the export contains live secrets "
    "(webhook URLs, API keys, etc.). File mode is 0600; the export "
    "directory's .gitignore is maintained to exclude these files."
)

# Field names whose values are treated as secrets. Match is case-insensitive
# against the full key. Deliberately permissive: false positives (redacting a
# non-secret) are acceptable; false negatives (leaking a secret) are not.
#
# Exact matches cover the handful of API field names that don't follow a common
# suffix pattern. Suffix matches cover future integration types without code
# changes (which is why this pattern-based approach exists in the first place).
#
# Extend by adding a regex. If you add a pattern broad enough to match a
# benign field in an existing integration response, add a test asserting the
# benign field survives (see test_non_secret_url_variants_are_not_over_redacted).
SECRET_FIELD_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        # Exact matches
        r'^password$',
        r'^secret$',
        r'^auth$',
        r'^credentials$',
        r'^bearer$',
        r'^url$',           # Slack API stores the webhook under `url`
        r'^webHookURL$',    # Teams API uses camelCase `webHookURL`
        # Suffix matches (trailing part of an underscore-delimited key)
        r'_key$',           # api_key, integration_key, opsgenie_key, service_key, routing_key
        r'_token$',         # auth_token, access_token, refresh_token, bearer_token
        r'_password$',      # smtp_password, basic_auth_password
        r'_secret$',        # client_secret
        r'_url$',           # webhook_url, any *_url (over-redaction is safer than under)
        r'_webhook$',
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
        # re.search so patterns like `_key$` match "ends with _key".
        # Exact-match patterns use explicit `^...$` anchors.
        return any(p.search(str(key)) for p in SECRET_FIELD_PATTERNS)


class AlertsExporter:
    """Fetch alert rules and integrations from AxonOps and write them as JSON.

    Single-cluster scope, mirroring `dashboard --exportpath` ergonomics.
    """

    def __init__(self, axonops, args):
        self.axonops = axonops
        self.args = args
        self.alert_rules = None
        self.integrations = None

    def fetch(self):
        """Hit both endpoints and store responses. Raises HTTPCodeError on failure."""
        org, cluster = self.args.org, self.args.cluster
        cluster_type = self.axonops.get_cluster_type()
        self.alert_rules = self.axonops.do_request(
            url=ALERT_RULES_URL.format(org=org, cluster_type=cluster_type, cluster=cluster),
            method='GET',
        ) or {}
        self.integrations = self.axonops.do_request(
            url=INTEGRATIONS_URL.format(org=org, cluster_type=cluster_type, cluster=cluster),
            method='GET',
        ) or {}

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
        # Atomic creation with restrictive mode. If a prior file exists with
        # permissive mode, tighten it BEFORE writing so the secret payload
        # never coexists with world-readable permissions (even transiently).
        if os.path.exists(path):
            os.chmod(path, 0o600)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f, indent=4)

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
        tmp_path = gitignore_path + ".tmp"
        with open(tmp_path, "w") as f:
            for line in existing_lines:
                f.write(line + "\n")
            for name in to_add:
                f.write(name + "\n")
        os.replace(tmp_path, gitignore_path)
