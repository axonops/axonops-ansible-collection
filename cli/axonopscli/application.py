import argparse
import os
import sys
from typing import Sequence

from .axonops import AxonOps
from .components.repair import AdaptiveRepair


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
            "repair",
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

        parsed_result: argparse.Namespace = parser.parse_args(args=argv)

        # if func() is not present it means that no command was inserted
        if hasattr(parsed_result, 'func'):
            self.run_mandatory_args_check(parsed_result)
            parsed_result.func(parsed_result)
        else:
            parser.print_help()

    def run_mandatory_args_check(self, args: argparse.Namespace):
        """ Check if mandatory variable are present """
        if not args.org or not args.cluster:
            print("The org and the cluster are mandatory")
            sys.exit(1)
        else:
            if args.v:
                print(f"Org: {args.org}")
                print(f"Cluster: {args.cluster}")

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
