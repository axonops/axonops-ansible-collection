"""Apply a tuned alert-rules JSON back to the live AxonOps cluster.

This closes the export → tune → apply loop. For each rule in the tuned
JSON's `metricrules[]` array, POST it to
`/api/v1/alert-rules/{org}/{cluster_type}/{cluster}`. The endpoint is
update-in-place keyed by rule `id`, so partial apply (stop on first
failure) is safe — the client can re-run after fixing the issue.

This is a destructive operation — it changes live alerting state that
affects paging. Callers must confirm explicitly (--yes) or interactively;
applying a file that contains the `***REDACTED***` sentinel is refused
unless --allow-redacted is set, because otherwise we would overwrite
live secret values (e.g. Slack webhook URLs embedded in dashboard
click-through annotations) with the literal string `***REDACTED***`.
"""

import json
from dataclasses import dataclass, field
from typing import List, Tuple

from axonopscli.api import ALERT_RULES_URL
from axonopscli.components.alerts import REDACTED


class RedactedInputError(Exception):
    """Raised when the input JSON contains the REDACTED sentinel and the
    caller has not explicitly opted in via --allow-redacted."""


# Minimum required fields on a rule for us to safely POST it.
# `id` is load-bearing: the API uses it for update-in-place semantics.
# The other fields are the minimum required by the alert-rule schema
# to produce a valid rule. We don't attempt to validate deeper — the
# server is the source of truth — we just guard against the obvious
# "empty object" or "forgot a field" mistakes.
_REQUIRED_FIELDS = ("id", "alert", "expr", "operator", "warningValue", "criticalValue")


def contains_redacted(obj) -> bool:
    """Recursively check if any string in the structure equals the exact
    REDACTED sentinel. Exact equality — substring matches don't count."""
    if isinstance(obj, str):
        return obj == REDACTED
    if isinstance(obj, dict):
        return any(contains_redacted(v) for v in obj.values())
    if isinstance(obj, list):
        return any(contains_redacted(item) for item in obj)
    return False


@dataclass
class ApplyResult:
    """Outcome of applying a tuned alert-rules JSON.

    - applied: rule identifiers successfully POSTed (or would-be-POSTed in dry-run).
    - failed:  (rule_name, error_message) for each POST that raised after
               --continue-on-error.
    - skipped: (rule_name, reason) for rules that didn't pass local validation.
    - dry_run: whether the run was a dry run (no network calls).
    """
    applied: List[str] = field(default_factory=list)
    failed: List[Tuple[str, str]] = field(default_factory=list)
    skipped: List[Tuple[str, str]] = field(default_factory=list)
    dry_run: bool = False


class AlertsApplier:
    """POST each rule in a tuned alert-rules JSON back to AxonOps.

    Single-cluster scope, mirroring the tune_alerts / alerts export ergonomics.
    """

    def __init__(self, axonops, args):
        self.axonops = axonops
        self.args = args

    def load_input(self, path: str) -> dict:
        """Read and validate the input JSON. Raises ValueError on any shape problem."""
        try:
            with open(path, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"input file {path!r} is not valid JSON: {e}")
        if not isinstance(data, dict):
            raise ValueError(
                f"input file {path!r} must contain a JSON object at top level, "
                f"got {type(data).__name__}"
            )
        if "metricrules" not in data or not isinstance(data["metricrules"], list):
            raise ValueError(
                f"input file {path!r} missing 'metricrules' list")
        return data

    def apply(
        self,
        input_json: dict,
        dry_run: bool,
        continue_on_error: bool,
        allow_redacted: bool,
    ) -> ApplyResult:
        """Apply each rule in input_json['metricrules'] to the cluster.

        Raises RedactedInputError if the input contains the REDACTED sentinel
        and allow_redacted is False. Raises HTTPCodeError on the first POST
        failure when continue_on_error is False.
        """
        if not allow_redacted and contains_redacted(input_json):
            raise RedactedInputError(
                "Input contains '***REDACTED***'. The export that produced "
                "this file was run without --include-secrets, so secret fields "
                "(e.g. dashboard click-through URLs in annotations) have been "
                "replaced by the sentinel. Applying it now would overwrite "
                "real values with the literal string '***REDACTED***' and "
                "break the affected integrations. Re-export with "
                "--include-secrets, or pass --allow-redacted to bypass this "
                "safety check."
            )

        result = ApplyResult(dry_run=dry_run)
        cluster_type = self.axonops.get_cluster_type()
        url = ALERT_RULES_URL.format(
            org=self.args.org,
            cluster_type=cluster_type,
            cluster=self.args.cluster,
        )

        for rule in input_json.get("metricrules", []):
            name = rule.get("alert", "<unnamed>")
            rule_id = rule.get("id")

            # Local validation: skip rules that can't safely round-trip.
            missing = [f for f in _REQUIRED_FIELDS if f not in rule]
            if missing:
                result.skipped.append((
                    name,
                    f"missing required field(s): {', '.join(missing)}",
                ))
                if getattr(self.args, "v", 0):
                    print(f"  [skipped]  {name}: missing {', '.join(missing)}")
                continue

            if dry_run:
                print(
                    f"[dry-run] POST {url} "
                    f"(rule id {rule_id}, alert \"{name}\")"
                )
                result.applied.append(name)
                continue

            try:
                self.axonops.do_request(url=url, method="POST", json_data=rule)
            except Exception as e:
                if not continue_on_error:
                    # Re-raise so the caller sees the full error. We deliberately
                    # don't swallow it — rollback isn't realistic, and the user
                    # needs the details.
                    raise
                result.failed.append((name, str(e)))
                if getattr(self.args, "v", 0):
                    print(f"  [failed]   {name}: {e}")
                continue

            result.applied.append(name)
            if getattr(self.args, "v", 0):
                print(f"  [applied]  {name} (id {rule_id})")

        return result

    def print_summary(self, result: ApplyResult) -> None:
        """Print the one-line summary. Verbose per-rule output is emitted
        during apply() itself so it interleaves with progress."""
        if result.dry_run:
            print(
                f"[dry-run] Would apply {len(result.applied)} rules to "
                f"{self.args.org}/{self.args.cluster}"
            )
            if result.skipped:
                print(f"  skipped {len(result.skipped)} rules (validation)")
            return

        parts = [f"Applied {len(result.applied)} rules"]
        parts.append(f"failed {len(result.failed)} rules")
        parts.append(f"skipped {len(result.skipped)} rules")
        print(", ".join(parts))

        if result.failed:
            print("Failures:")
            for name, err in result.failed:
                print(f"  - {name}: {err}")
        if result.skipped:
            print("Skipped:")
            for name, reason in result.skipped:
                print(f"  - {name}: {reason}")
