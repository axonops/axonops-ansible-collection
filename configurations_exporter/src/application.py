"""Command line surface of the AxonOps Configurations Exporter."""

import argparse
import os
import sys
from typing import Any, Dict, List, Sequence, Tuple

from . import VERSION
from .axonops import DEFAULT_CLUSTER_TYPE, AxonOps
from .cli_script import render_env_file, render_script
from .clusters import Cluster, discover_clusters
from .exporter import Exporter, org_directory
from .urls import SECTION_NAMES
from .utils import APIConnectionError, ExporterError, HTTPCodeError, safe_filename, write_file


class Application:
    """Parses the command line and dispatches to the matching handler."""

    def __init__(self):
        self.axonops = None

    def get_axonops(self, args: argparse.Namespace) -> AxonOps:
        """Build the API client once and reuse it for the whole run."""
        if self.axonops is None:
            self.axonops = AxonOps(args.org,
                                   base_url=args.url,
                                   username=args.username,
                                   password=args.password,
                                   cluster_type=args.cluster_type,
                                   api_token=args.token,
                                   verbose=args.v)
        return self.axonops

    def build_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog='configurations_exporter',
            description="AxonOps Configurations Exporter - A tool to export configurations from AxonOps"
        )

        parser.add_argument('--version', action='version', version=f"%(prog)s {VERSION}")

        parser.add_argument('--org', type=str, required=False, default=os.getenv('AXONOPS_ORG'),
                            help='Name of your organisation')
        parser.add_argument('--cluster', type=str, required=False, default=os.getenv('AXONOPS_CLUSTER'),
                            help='Name of your cluster. If omitted, every cluster of the '
                                 'organisation is exported')
        parser.add_argument('--cluster-type', type=str, required=False,
                            default=os.getenv('AXONOPS_CLUSTER_TYPE', DEFAULT_CLUSTER_TYPE),
                            help=f"Type of the cluster, for example cassandra, dse or kafka "
                                 f"(default: {DEFAULT_CLUSTER_TYPE}). Ignored without --cluster, "
                                 f"where each cluster carries the type the API reports for it")
        parser.add_argument('--token', type=str, required=False, default=os.getenv('AXONOPS_TOKEN'),
                            help='AUTH_TOKEN used to authenticate with the API in SaaS')
        parser.add_argument('--username', type=str, required=False, default=os.getenv('AXONOPS_USERNAME'),
                            help='Username used for AxonOps Self-Hosted when authentication is enabled')
        parser.add_argument('--password', type=str, required=False, default=os.getenv('AXONOPS_PASSWORD'),
                            help='Password used for AxonOps Self-Hosted when authentication is enabled')
        parser.add_argument('--url', type=str, default=os.getenv('AXONOPS_URL'),
                            help='Specify the AxonOps URL if not using the AxonOps Cloud environment')

        parser.add_argument('-v', '--verbose', dest='v', action='count', default=0, help='Verbosity')

        commands_subparser = parser.add_subparsers(help='commands')

        export_parser = commands_subparser.add_parser(
            'export',
            help="Export the configuration of a cluster")
        export_parser.set_defaults(func=self.run_export)

        export_parser.add_argument('--section', dest='sections', action='append', metavar='NAME',
                                   help=f"Export only this section, repeatable. "
                                        f"One of: {', '.join(SECTION_NAMES)}")
        export_parser.add_argument('--fail-on-error', action='store_true',
                                   help='Abort the export when the API rejects a section, '
                                        'instead of skipping it')

        sections_parser = commands_subparser.add_parser(
            'sections',
            help='List the configuration sections this tool can export')
        sections_parser.set_defaults(func=self.run_sections)

        return parser

    def run(self, argv: Sequence[str]) -> int:
        parser = self.build_parser()
        args = parser.parse_args(args=argv)

        if not hasattr(args, 'func'):
            parser.print_help()
            return 1

        try:
            return args.func(args)
        except (ExporterError, HTTPCodeError, APIConnectionError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    def run_mandatory_args_check(self, args: argparse.Namespace) -> None:
        """Verify the options every API call depends on are present."""
        if not args.org:
            raise ExporterError("The org is mandatory")

        # Credentials are optional: a self-hosted axon-server may have
        # authentication disabled, which is the default for a local instance.
        if args.v:
            print(f"Org: {args.org}", file=sys.stderr)
            print(f"Cluster: {args.cluster or 'every cluster of the organisation'}",
                  file=sys.stderr)

    def resolve_clusters(self, args: argparse.Namespace) -> List[Cluster]:
        """The clusters to export: the named one, or every cluster of the org."""
        if args.cluster:
            return [Cluster(args.org, args.cluster_type, args.cluster)]

        if args.v:
            print("No --cluster given, asking the API for the clusters of the organisation",
                  file=sys.stderr)

        clusters = discover_clusters(self.get_axonops(args), org=args.org)
        if not clusters:
            raise ExporterError(f"No cluster found for the org '{args.org}'")

        return clusters

    def run_sections(self, _args: argparse.Namespace) -> int:
        """List the exportable configuration sections."""
        for name in SECTION_NAMES:
            print(name)
        return 0

    def run_export(self, args: argparse.Namespace) -> int:
        """Run the configuration export."""
        self.run_mandatory_args_check(args)

        axonops = self.get_axonops(args)
        clusters = self.resolve_clusters(args)

        by_org: Dict[str, List[Tuple[Cluster, Dict[str, Any]]]] = {}
        for cluster in clusters:
            exporter = Exporter(axonops,
                                org=cluster.org,
                                cluster=cluster.name,
                                cluster_type=cluster.cluster_type,
                                sections=args.sections,
                                verbose=args.v,
                                ignore_errors=not args.fail_on_error)

            configuration = exporter.fetch()
            exporter.write(configuration)
            by_org.setdefault(cluster.org, []).append((cluster, configuration))

        for org, exports in by_org.items():
            self.write_cli_settings(args, org, exports)

        if len(clusters) > 1:
            print(f"Exported {len(clusters)} clusters", file=sys.stderr)

        return 0

    def write_cli_settings(self, args: argparse.Namespace, org: str,
                           exports: List[Tuple[Cluster, Dict[str, Any]]]) -> None:
        """Write the CLI environment file and the script that replays the export."""
        directory = org_directory(org)

        env_path = os.path.join(directory, '.env.axonops')
        write_file(env_path, render_env_file(org, url=args.url, cluster=args.cluster,
                                             username=args.username))

        script_path = os.path.join(directory, f"{safe_filename(org)}.sh")
        write_file(script_path, render_script(org, exports))

        print(f"Wrote the CLI settings to {env_path} and {script_path}", file=sys.stderr)
