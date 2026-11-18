"""Small helpers shared across the exporter."""

import os
import re


class HTTPCodeError(Exception):
    """Raised when the AxonOps API answers with an unexpected status code."""


class APIConnectionError(Exception):
    """Raised when the AxonOps API cannot be reached at all."""


class ExporterError(Exception):
    """Raised for user-facing errors that should abort the export."""


def safe_filename(name: str) -> str:
    """Turn an arbitrary name into something safe to use as a path segment.

    Path separators and any other unexpected character become an underscore, and
    leading dots are dropped so a name like `..` cannot escape its directory.
    """
    cleaned = re.sub(r'[^A-Za-z0-9._-]+', '_', name).strip('._-')
    return cleaned or 'unnamed'


def write_file(path: str, content: str) -> None:
    """Write `content` to `path`, creating the directories it needs."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as handle:
        handle.write(content)
