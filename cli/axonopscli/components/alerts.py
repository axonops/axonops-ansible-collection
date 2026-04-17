import json
import os
import re

REDACTED = "***REDACTED***"
GITIGNORE_FILENAME = ".gitignore"
SECRETS_WARNING = (
    "WARNING: --include-secrets is set; the export contains live secrets "
    "(webhook URLs, API keys, etc.). File mode is 0600 and the export "
    "directory's .gitignore has been updated to exclude these files."
)

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
