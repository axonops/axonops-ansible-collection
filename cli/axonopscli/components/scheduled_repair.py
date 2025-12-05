class ScheduledRepair:
    """ Class to manage the Scheduled Repair in AxonOps """
    schedule_repair_add_url = "/api/v1/addrepair"

    def __init__(self, axonops, args):
        self.axonops = axonops
        self.args = args
        self.repair_data = None
        self.full_url = f"{self.schedule_repair_add_url}/{args.org}/cassandra/{args.cluster}"

    def set_options(self):
        """Apply optional CLI parameters into the payload before sending it."""
        if self.args.v:
            print("Setting scheduled repair options")

        self.repair_data = {
            "keyspace": self.args.keyspace or "",
            "tables": self.args.tables.split(",") if self.args.tables else [],
            "blacklistedTables": self.args.excludedtables.split(",") if self.args.excludedtables else [],
            "nodes": self.args.nodes.split(",") if self.args.nodes else [],
            "segmentsPerNode": self.args.segmentspernode or 1,
            "segmented": self.args.segmented or False,
            "incremental": self.args.incremental or False,
            "jobThreads": self.args.jobthreads or 1,
            "schedule": True,
            "scheduleExpr": "0 * * 1 *",  # Default to run monthly at midnight
            "primaryRange": self.args.partitionerrange or False,
            "parallelism": self.args.parallelism or "Parallel",
            "optimiseStreams": self.args.optimisestreams or False,
            "specificDataCenters": self.args.datacenters.split(",") if self.args.datacenters else [],
            "tag": self.args.tags or "",
            "paxos": "Default",
            "skipPaxos": False,
            "paxosOnly": False
        }

        if self.args.scheduleexpr:
            if self.args.v:
                print("Setting ScheduleExpr to", self.args.scheduleexpr)
                print("Setting Schedule to True")
            self.repair_data['schedule'] = True
            self.repair_data['scheduleExpr'] = self.args.scheduleexpr
        else:
            if self.args.v:
                print("No ScheduleExpr provided, using default:", self.repair_data['scheduleExpr'])
                print("Setting Schedule to False")
            self.repair_data['schedule'] = False

        if self.args.skippaxos:
            if self.args.v:
                print("Setting SkipPaxos to True")
            self.repair_data['skipPaxos'] = True
            self.repair_data['paxos'] = "Skip Paxos"

        if self.args.paxosonly:
            if self.args.v:
                print("Setting PaxosOnly to True")
            self.repair_data['paxosOnly'] = True
            self.repair_data['paxos'] = "Paxos Only"

    def set_repair(self):
        full_url = f"{self.axonops.dash_url()}{self.schedule_repair_add_url}"
        print("Setting the scheduled repair")
        if self.args.v:
            print("POST", self.full_url, self.repair_data)

        self.axonops.do_request(
            url=self.full_url,
            method='POST',
            json_data=self.repair_data,
        )
