"""Fetch AxonOps configuration and render it as YAML."""

import os
import sys
from typing import Any, Dict, List, Optional

import yaml

from .axonops import AxonOps
from .urls import SECTIONS, cluster_url
from .utils import ExporterError, HTTPCodeError, safe_filename, write_file

# Every export is written under this directory, one file per section, in
# `<EXPORT_ROOT>/<org>/<cluster>/<section>.yaml`.
EXPORT_ROOT = "exports"


def org_directory(org: str) -> str:
    """Directory holding everything exported for one organisation."""
    return os.path.join(EXPORT_ROOT, safe_filename(org))


class Exporter:
    """Reads the configuration of one cluster and writes it out as YAML."""

    def __init__(self, axonops: AxonOps, org: str, cluster: str,
                 cluster_type: Optional[str] = None,
                 sections: Optional[List[str]] = None, verbose: int = 0,
                 ignore_errors: bool = True):
        self.axonops = axonops
        self.org = org
        self.cluster = cluster
        self.cluster_type = cluster_type or axonops.get_cluster_type()
        self.sections = sections or list(SECTIONS)
        self.verbose = verbose
        self.ignore_errors = ignore_errors
        self.skipped: List[str] = []

        unknown = [name for name in self.sections if name not in SECTIONS]
        if unknown:
            raise ExporterError(f"Unknown section(s): {', '.join(unknown)}. "
                                f"Known sections: {', '.join(SECTIONS)}")

    def fetch(self) -> Dict[str, Any]:
        """Fetch every requested section and return them keyed by section name.

        A section the API rejects is skipped and recorded in `self.skipped`, unless
        the caller asked for `ignore_errors=False`.
        """
        exported: Dict[str, Any] = {}
        self.skipped = []

        for name in self.sections:
            endpoint, query = SECTIONS[name]
            url = cluster_url(endpoint, self.org, self.cluster_type, self.cluster, query)

            if self.verbose:
                print(f"Exporting {name} of {self.cluster}", file=sys.stderr)

            try:
                exported[name] = self.axonops.do_request(url)
            except HTTPCodeError as exc:
                if not self.ignore_errors:
                    raise ExporterError(
                        f"{exc}\nThe '{name}' section may not be available on this AxonOps "
                        f"version or cluster.") from exc
                self.skipped.append(name)
                print(f"Skipping {name} of {self.cluster}: {exc}", file=sys.stderr)

        return exported

    def document(self, exported: Dict[str, Any]) -> Dict[str, Any]:
        """Wrap the exported sections with the context they were read from."""
        return {
            'org': self.org,
            'cluster': self.cluster,
            'cluster_type': self.cluster_type,
            'configuration': exported,
        }

    def output_directory(self) -> str:
        """Directory this export is written to."""
        return os.path.join(org_directory(self.org), safe_filename(self.cluster))

    def write(self, exported: Dict[str, Any]) -> None:
        """Write one YAML file per section into the export directory."""
        directory = self.output_directory()
        os.makedirs(directory, exist_ok=True)

        for name, payload in exported.items():
            path = os.path.join(directory, f"{safe_filename(name)}.yaml")
            write_file(path, self._dump(self.document({name: payload})))
            if self.verbose:
                print(f"Wrote {path}", file=sys.stderr)

        skipped = f", {len(self.skipped)} skipped ({', '.join(self.skipped)})" if self.skipped else ""
        print(f"Exported {len(exported)} section(s) to {directory}/{skipped}", file=sys.stderr)

    @staticmethod
    def _dump(document: Dict[str, Any]) -> str:
        return yaml.safe_dump(document, default_flow_style=False, sort_keys=False, allow_unicode=True)
