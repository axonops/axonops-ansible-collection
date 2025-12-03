# {"keyspace":"","tables":[],"blacklistedTables":[],"nodes":[],"segmentsPerNode":2,"segmented":false,
# "incremental":false,"jobThreads":1,"schedule":false,"scheduleExpr":"0 * * 1 *","primaryRange":false,
# "parallelism":"Parallel","optimiseStreams":false,"specificDataCenters":[],"tag":"","paxos":"Default",
# "skipPaxos":false,"paxosOnly":false}

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
            "segmentsPerNode": self.args.segmentspernode or 2,
            "segmented": self.args.segmented or False,
            "incremental": self.args.incremental or False,
            "jobThreads": 1,
            "schedule": True,
            "scheduleExpr": "0 * * 1 *",  # Default to run monthly at midnight
            "primaryRange": False,
            "parallelism": "Parallel",
            "optimiseStreams": False,
            "specificDataCenters": [],
            "tag": "",
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
