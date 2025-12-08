from axonopscli.axonops import HTTPCodeError


class ScheduledRepair:
    """ Class to manage the Scheduled Repair in AxonOps """
    schedule_repair_add_url = "/api/v1/addrepair"
    repair_url = "/api/v1/repair"
    cassandrascheduledrepair_url = "/api/v1/cassandrascheduledrepair"

    def __init__(self, axonops, args):
        self.axonops = axonops
        self.args = args
        self.repair_data = None
        self.full_add_repair_url = f"{self.schedule_repair_add_url}/{args.org}/cassandra/{args.cluster}"
        self.full_repair_url = f"{self.repair_url}/{args.org}/cassandra/{args.cluster}"
        self.full_cassandrascheduledrepair_url = f"{self.cassandrascheduledrepair_url}/{args.org}/cassandra/{args.cluster}"

    def remove_old_repairs_from_axonops(self):
        """ Check if the scheduled repair already exists in AxonOps, if so, remove it. """
        if self.args.v:
            print("Checking if scheduled repair already exists")

        if self.args.tags != "":
            if self.args.v:
                print("Getting scheduled repair with tag:", self.args.tags)
            response = self.axonops.do_request(
                url=self.full_repair_url,
                method='GET',
            )
            if not response:
                if self.args.v:
                    print("No response received when checking for existing scheduled repair")
                return
            elif 'ScheduledRepairs' in response and response['ScheduledRepairs']:
                for repair in response['ScheduledRepairs']:
                    if self.args.v:
                        print(f"Checking scheduled repair: {repair['ID']}")
                    self.remove_repair(repair['ID'])
                    if 'Params' in repair:
                        print(repair['Params'])

            else:
                print("Repair tag not found, this will be threaded as a new scheduled repair")
        else:
            if self.args.v:
                print("No tag provided, this will be threaded as a new scheduled repair")

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
        print("Setting the scheduled repair")
        if self.args.v:
            print("POST", self.full_add_repair_url, self.repair_data)

        if self.args.delete:
            if self.args.v:
                print("This scheduled repair is delete, not sending to AxonOps")
            return

        self.axonops.do_request(
            url=self.full_add_repair_url,
            method='POST',
            json_data=self.repair_data,
        )

    def remove_repair(self, repair_id: str) -> bool:
        """ Remove a scheduled repair from AxonOps by its ID. """
        if self.args.v:
            print(f"Removing scheduled repair with ID: {repair_id}")

        try:
            response = self.axonops.do_request(
                url=f"{self.full_cassandrascheduledrepair_url}?id={repair_id}",
                method='DELETE',
            )
        except HTTPCodeError:
            print(f"Failed to remove scheduled repair with ID: {repair_id}")
            raise
        else:
            if self.args.v:
                print(f"Response received when removing scheduled repair with ID: {repair_id}: {response}")

            return True
