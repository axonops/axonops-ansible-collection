import argparse
import os
import sys
from typing import Sequence

from .axonops import AxonOps
from .components.dashboard import Dashboard
from .components.repair import AdaptiveRepair
from .components.scheduled_repair import ScheduledRepair
from .utils import remove_not_alphanumeric


class Application:

    def __init__(self):
        """
        This object represents the main application
        """
        self.axonops = None
        # the option taken from the files and argv parameter
        # self.options:dict[str, str] = {}

    def get_axonops(self, args):
        if self.axonops is None:
            self.axonops = AxonOps(args.org,
                                   api_token=args.token,
                                   base_url=args.url,
                                   username=args.username,
                                   password=args.password,
                                   cluster_type=args.cluster,
                                   verbose=args.v)
        return self.axonops

    def run(self, argv: Sequence):

        parser = argparse.ArgumentParser(description='AxonOps Adaptive Repair CLI')

        parser.add_argument('--org', type=str, required=False, default=os.getenv('AXONOPS_ORG'),
                            help='Name of your organisation')
        parser.add_argument('--cluster', type=str, required=False, default=os.getenv('AXONOPS_CLUSTER'),
                            help='Name of your cluster')
        parser.add_argument('--token', type=str, required=False, default=os.getenv('AXONOPS_TOKEN'),
                            help='AUTH_TOKEN used to authenticate with the API in SaaS')
        parser.add_argument('--username', type=str, required=False, default=os.getenv('AXONOPS_USERNAME'),
                            help='Username used for AxonOps Self-Hosted when authentication is enabled')
        parser.add_argument('--password', type=str, required=False, default=os.getenv('AXONOPS_PASSWORD'),
                            help='Password used for AxonOps Self-Hosted when authentication is enabled')
        parser.add_argument('--url', type=str, default=os.getenv('AXONOPS_URL'),
                            help='Specify the AxonOps URL if not using the AxonOps Cloud environment')

        parser.add_argument("-v", action='count', default=0, help="Verbosity")

        commands_subparser = parser.add_subparsers(help="commands")

        adaptive_repair_parser = commands_subparser.add_parser(
            "repair", aliases=['adaptiverepair'],
            help="Manage the Adaptive Repair in AxonOps")
        adaptive_repair_parser.set_defaults(func=self.run_adaptive_repair)

        adaptive_repair_parser.add_argument('--enabled', action='store_true',
                                            help='Enables AxonOps Adaptive Repair')

        adaptive_repair_parser.add_argument('--disabled', action='store_true',
                                            help='Disable AxonOps Adaptive Repair')

        adaptive_repair_parser.add_argument('--gcgrace', type=int, required=False,
                                            help='GG Grace Threshold in Seconds')

        adaptive_repair_parser.add_argument('--tableparallelism', type=int, required=False,
                                            help='Concurrent Repair Processes')

        adaptive_repair_parser.add_argument('--maxsegmentspertable', type=int, required=False,
                                            help='Max Segments per Table')

        adaptive_repair_parser.add_argument('--segmentretries', type=int, required=False,
                                            help='Segment Retries')

        adaptive_repair_parser.add_argument('--excludedtables', type=str, required=False,
                                            help='Comma-separated list of table excluded from the Adapted Repair')

        adaptive_repair_parser.add_argument('--excludetwcstables', type=str, required=False,
                                            help='Exclude TWCS tables from the Adaptive Repair. true/false default true')

        adaptive_repair_parser.add_argument('--segmenttargetsizemb', type=int, required=False,
                                            help='Segment Target Size in MB')

        adaptive_repair_parser.add_argument('--segmenttimeout', type=str, required=False,
                                            help='Segment Timeout. Integer number followed by one of "s, m, h, d, w, M, y"')

        scheduledrepair_parser = commands_subparser.add_parser(
            "scheduledrepair",
            help="Manage the Scheduled Repair in AxonOps")
        scheduledrepair_parser.set_defaults(func=self.run_scheduled_repair)

        scheduledrepair_parser.add_argument('--keyspace', type=str, required=False,
                                            help='Keyspace to repair. If empty, all keyspaces are repaired')
        scheduledrepair_parser.add_argument('--tables', type=str, required=False,
                                            help='Comma-separated list of tables to repair in the selected keyspace. If empty, all tables are repaired')
        scheduledrepair_parser.add_argument('--excludedtables', type=str, required=False,
                                            help='Comma-separated list of tables to exclude from repair')
        scheduledrepair_parser.add_argument('--nodes', type=str, required=False,
                                            help='Comma-separated list of nodes to repair')
        scheduledrepair_parser.add_argument('--segmentspernode', type=int, required=False,
                                            help='Number of segments per node')
        scheduledrepair_parser.add_argument('--segmented', action='store_true',
                                            help='Enable segmented repair')
        scheduledrepair_parser.add_argument('--incremental', action='store_true',
                                            help='Enable incremental repair')
        scheduledrepair_parser.add_argument('--jobthreads', type=int, required=False, default=1,
                                            help='Number of job threads')
        scheduledrepair_parser.add_argument('--scheduleexpr', type=str, required=False,
                                            help='Cron expression for scheduling the repair')
        scheduledrepair_parser.add_argument('--partitionerrange', action='store_true',
                                            help='Enable partitioner range repair')
        scheduledrepair_parser.add_argument('--parallelism', type=self._normalize_parallelism, required=False,
                                            default="Parallel",
                                            help='Parallelism type: Sequential, Parallel, DC-Aware')
        scheduledrepair_parser.add_argument('--optimisestreams', action='store_true',
                                            help='Enable stream optimization (only for Cassandra 4.1 and above)')
        scheduledrepair_parser.add_argument('--datacenters', type=str, required=False,
                                            help='Comma-separated list of datacenters to repair, if not specified all datacenters are included')
        scheduledrepair_parser.add_argument('--tags', type=str, required=False,
                                            help='Tag for the repair job', default="")
        scheduledrepair_parser.add_argument('--delete', action='store_true',
                                            help='Delete the scheduled repair instead of enabling it')
        scheduledrepair_parser.add_argument('--deleteall', action='store_true',
                                            help='Delete all scheduled repairs')

        paxos_group = scheduledrepair_parser.add_mutually_exclusive_group()
        paxos_group.add_argument('--paxosonly', action='store_true', default=False,
                                 help='Run only Paxos repairs')
        paxos_group.add_argument('--skippaxos', action='store_true', default=False,
                                 help='Skip Paxos repairs')

        dashboard_parser = commands_subparser.add_parser(
            "dashboard",
            help="Manage the AxonOps Dashboards")

        dashboard_parser.set_defaults(func=self.run_dashboard)

        dashboard_parser.add_argument('--list', action='store_true',
                                      help='List all dashboards for the specified cluster')
        file_dash_group = dashboard_parser.add_mutually_exclusive_group()
        file_dash_group.add_argument('--exportpath', type=str, required=False,
                                     help='Path to export dashboards to JSON files')
        file_dash_group.add_argument('--importfile', type=str, required=False,
                                     help='File path to import dashboard from a JSON file')
        dashboard_parser.add_argument('--dashboardname', type=str, required=False,
                                      help='Name of the dashboard to export or delete')
        dashboard_parser.add_argument('--deletedashboard', type=str, required=False,
                                      help='Delete the specified dashboard from AxonOps')
        dashboard_parser.add_argument('--position', type=int, required=False,
                                      help='Position of the dashboard in the list (used for import)')
        dashboard_parser.add_argument('--overwrite', action='store_true',
                                      help='Overwrite existing dashboard when importing')

        parsed_result: argparse.Namespace = parser.parse_args(args=argv)

        # ensure --tables is only used together with --keyspace
        if getattr(parsed_result, "tables", None) and not getattr(parsed_result, "keyspace", None):
            parser.error("--tables requires --keyspace")

        # ensure --disabled is only used together with tags
        if getattr(parsed_result, "delete", None) and not getattr(parsed_result, "tags", None):
            parser.error("--delete requires --tags")

        # ensure --excludedtables is only used together with --keyspace
        if getattr(parsed_result, "excludedtables", None) and not getattr(parsed_result, "keyspace", None):
            parser.error("--excludedtables requires --keyspace")

        # if func() is not present it means that no command was inserted
        if hasattr(parsed_result, 'func'):
            self.run_mandatory_args_check(parsed_result)
            parsed_result.func(parsed_result)
        else:
            parser.print_help()

    def _normalize_parallelism(self, value: str) -> str:
        """ Normalize and validate parallelism input """
        choices = ["Sequential", "Parallel", "DC-Aware"]
        for c in choices:
            if remove_not_alphanumeric(value.lower()) == remove_not_alphanumeric(c.lower()):
                return c
        raise argparse.ArgumentTypeError(f"Invalid parallelism: {value}. Choose one of: {', '.join(choices)}")

    def run_mandatory_args_check(self, args: argparse.Namespace):
        """ Check if mandatory variable are present """
        if not args.org or not args.cluster:
            print("The org and the cluster are mandatory")
            sys.exit(1)
        else:
            if args.v:
                print(f"Org: {args.org}")
                print(f"Cluster: {args.cluster}")

    def run_dashboard(self, args: argparse.Namespace):
        """ Run the dashboard management """
        if args.v:
            print(f"Running dashboard management on {args.org}")
            print(args)

        axonops = self.get_axonops(args)

        dashboard = Dashboard(axonops, args)
        dashboard.get_actual_dashboards()
        if args.list:
            dashboard.list_dashboards()
        elif args.exportpath:
            dashboard.export_dashboard(args.exportpath, args.dashboardname)
        elif args.importfile:
            dashboard.import_dashboard(args.importfile, args.dashboardname, args.position, args.overwrite)
        elif args.deletedashboard:
            dashboard.delete_dashboard(args.deletedashboard)
        else:
            print("No action specified for dashboard management.")

    def run_adaptive_repair(self, args: argparse.Namespace):
        """ Run the adaptive repair """
        if args.v:
            print(f"Running repairs on {args.org}")
            print(args)

        # input checking
        if args.enabled and args.disabled:
            print("The option enabled and disabled are mutually exclusive, you can't choose both at the same time.")
            sys.exit(1)

        if not args.enabled and not args.disabled:
            print("At least one option enabled or disabled should be present.")
            sys.exit(1)

        axonops = self.get_axonops(args)

        adaptive_repair = AdaptiveRepair(args, axonops)

        adaptive_repair.get_actual_repair()

        adaptive_repair.check_repair_status()

        adaptive_repair.check_repair_active()

        adaptive_repair.set_options()

        adaptive_repair.set_repair()

    def run_scheduled_repair(self, args: argparse.Namespace):
        """ Run the scheduled repair """
        if args.v:
            print(f"Running scheduled repairs on {args.org}")
            print(args)

        axonops = self.get_axonops(args)

        scheduled_repair = ScheduledRepair(axonops, args)

        if args.deleteall:
            scheduled_repair.remove_all_repairs_from_axonops()
            return

        scheduled_repair.set_options()

        scheduled_repair.set_repair()
