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
