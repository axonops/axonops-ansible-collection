import argparse

from axonopscli.axonops import AxonOps


class AdaptiveRepair:
    """
    This class manages the logic for the adaptive repair.
    """
    adaptive_repair_url = "/api/v1/adaptiveRepair"

    def __init__(self, args: argparse.Namespace, axonops: AxonOps):
        self.args = args
        self.axonops = axonops
        self.repair_data = None
        self.full_url = f"{self.adaptive_repair_url}/{args.org}/cassandra/{args.cluster}"

    def get_actual_repair(self):
        if self.repair_data is None:
            if self.args.v:
                print("Getting actual repair")
                print("GET", self.full_url)

            self.repair_data = self.axonops.do_request(
                url=self.full_url,
                method='GET',
            )
        return self.repair_data

    def check_repair_status(self):
        """ Check if the repair is failing and why"""
        if not self.repair_data['Ready']:
            print("The repair is not ready")
            if self.repair_data['NotReadyReason']:
                print("Reason:", self.repair_data['NotReadyReason'])

    def check_repair_active(self):
        """ Check if the repair needs to be enabled/disabled"""
        if self.args.v:
            print("Actual", self.repair_data['Active'])
            print("Enabled", self.args.enabled)
            print("Disabled", self.args.disabled)

        if not self.repair_data['Active'] and self.args.enabled:
            print("The repair is currently disabled, it needs to be enabled. Enabling it")
            self.repair_data['Active'] = True

        if self.repair_data['Active'] and self.args.disabled:
            print("The repair is currently enabled, it needs to be disabled. Disabling it")
            self.repair_data['Active'] = False

    def set_options(self):
        """Apply optional CLI parameters into the payload before sending it."""

        if getattr(self.args, 'gcgrace', None) is not None:
            print("Setting GcGraceThreshold to", self.args.gcgrace, "seconds")
            self.repair_data['GcGraceThreshold'] = self.args.gcgrace

        if getattr(self.args, 'maxsegmentspertable', None) is not None:
            print("Setting MaxSegmentsPerTable to", self.args.maxsegmentspertable)
            self.repair_data['MaxSegmentsPerTable'] = self.args.maxsegmentspertable

        if getattr(self.args, 'tableparallelism', None) is not None:
            print("Setting TableParallelism to", self.args.tableparallelism)
            self.repair_data['TableParallelism'] = self.args.tableparallelism

        if getattr(self.args, 'segmentretries', None) is not None:
            print("Setting SegmentRetries to", self.args.segmentretries)
            self.repair_data['SegmentRetries'] = self.args.segmentretries

        if getattr(self.args, 'excludedtables', None) is not None:
            tables_args = self.args.excludedtables.split(',')
            self.repair_data['BlacklistedTables'] = []
            for table in tables_args:
                if table not in self.repair_data['BlacklistedTables']:
                    self.repair_data['BlacklistedTables'].append(table.strip())
            print("Setting excludedtables to", self.repair_data['BlacklistedTables'])

        if getattr(self.args, 'excludetwcstables', None) is not None:
            print("Setting excludetwcstables to", self.args.excludetwcstables)
            self.repair_data['FilterTWCSTables'] = self.args.excludetwcstables

        if getattr(self.args, 'segmenttargetsizemb', None) is not None:
            print("Setting SegmentTargetSizeMB to", self.args.segmenttargetsizemb)
            self.repair_data['SegmentTargetSizeMB'] = self.args.segmenttargetsizemb

        if getattr(self.args, 'segmenttimeout', None) is not None:
            print("Setting SegmentTimeout to", self.args.segmenttimeout)
            self.repair_data['SegmentTimeout'] = self.args.segmenttimeout

    def set_repair(self):

        if self.args.v:
            print("POST", self.full_url, self.repair_data)

        self.axonops.do_request(
            url=self.full_url,
            method='POST',
            json_data=self.repair_data,
        )
