from .nodes import Nodes


class Silence:
    silence_window_url = "/api/v1/silenceWindow"

    def __init__(self, axonops, args):
        self.axonops = axonops
        self.args = args
        self.full_url = f"{self.silence_window_url}/{self.args.org}/cassandra/{self.args.cluster}"

        self.nodes = Nodes(axonops, args)

    def delete_silence(self, id_argument: str):
        delete_url = f"{self.full_url}/{id_argument}"
        print("Deleting silence with ID:", id_argument)
        if self.args.v:
            print("DELETE", delete_url)
        self.axonops.do_request(
            url=delete_url,
            method='DELETE',
        )

    def create_silence(self):
        silenceall = True
        if self.args.silencemetricsalerts \
                or self.args.silenceservicechecksalerts \
                or self.args.silenceeventalerts \
                or self.args.silencebackupalerts \
                or self.args.silencebackuprestorealerts \
                or self.args.silenceauditalerts \
                or self.args.silenceadaptiverepairalerts \
                or self.args.silencegenericalerts \
                or self.args.silencegenerictaskalerts \
                or self.args.silencelogalerts \
                or self.args.silencenodealerts \
                or self.args.silencerepairalerts \
                or self.args.silencerollingrestartalerts \
                or self.args.silencescheduledreportsalerts:
            silenceall = False

        payload = {
            "Duration": self.args.duration,
            "CronExpr": self.args.cronexpr or '0 * * * *',
            "SilenceAll": silenceall,
            "DCs": self.args.dcs if self.args.dcs else [],
            "MetricsAlerts": self.args.silencemetricsalerts,
            "ServiceChecksAlerts": self.args.silenceservicechecksalerts,
            "EventAlerts": self.args.silenceeventalerts,
            "BackupAlerts": self.args.silencebackupalerts,
            "BackupRestoreAlerts": self.args.silencebackuprestorealerts,
            "AuditAlerts": self.args.silenceauditalerts,
            "AdaptiveRepairAlerts": self.args.silenceadaptiverepairalerts,
            "GenericAlerts": self.args.silencegenericalerts,
            "GenericTaskAlerts": self.args.silencegenerictaskalerts,
            "LogAlerts": self.args.silencelogalerts,
            "NodeAlerts": self.args.silencenodealerts,
            "RepairAlerts": self.args.silencerepairalerts,
            "RollingRestartAlerts": self.args.silencerollingrestartalerts,
            "ScheduledReportsAlerts": self.args.silencescheduledreportsalerts
        }
        if self.args.cronexpr:
            print("Creating a recurring silence with cron expression:", self.args.cronexpr)
            payload['IsRecurring'] = True
        if self.args.v:
            print("Creating silence")
            print("POST", self.full_url)
            print("Payload:", payload)

        response = self.axonops.do_request(
            url=self.full_url,
            method='POST',
            json_data=payload
        )
        if self.args.v:
            print("Response:", response)
        if response and 'id' in response:
            print(f"Silence created with ID: {response['id']}")
        else:
            print("Failed to create silence")

    def list_silences(self):

        if self.args.v:
            print("Getting silences")
            print("GET", self.full_url)

        response = self.axonops.do_request(
            url=self.full_url,
            method='GET',
        )
        if not response:
            print("No silences found")
            return
        else:
            if self.args.v:
                print(f"Found {len(response)} silences")
                print(response)

            for silence in response:
                print("-" * 40)
                if silence['IsRecurring']:
                    print(f"ID: {silence['ID']}, Duration: {silence['Duration']}, CronExpr: {silence['CronExpr']}",
                          end="")
                else:
                    print(f"ID: {silence['ID']}, Duration: {silence['Duration']}", end=""),
                if silence['LastRun'] and silence['LastRun'] != "0001-01-01T00:00:00Z":
                    print(f", LastRun: {silence['LastRun']}", end="")
                if silence['NextRun'] and silence['NextRun'] != "0001-01-01T00:00:00Z":
                    print(f", NextRun: {silence['NextRun']}", end="")
                if 'DCs' in silence and silence['DCs']:
                    print("\nDCs:", end="")
                    for dc in silence['DCs']:
                        print(f"\n- {dc['Name']}", end="")
                        if 'Racks' in dc and dc['Racks']:
                            print("\n    Racks:", end="")
                            for rack in dc['Racks']:
                                print(f"\n     - {rack['Name']}", end="")
                                if 'Nodes' in rack and rack['Nodes']:
                                    print(f"\n         Nodes:", end="")
                                    for node in rack['Nodes']:
                                        print(f"\n          - {self.nodes.print_by_id(node)}", end="")
                                else:
                                    print(f"\n         All Nodes", end="")
                        else:
                            print(f"\n    All Racks and Nodes", end="")
                    print(f"\n\n", end="")
                if silence['SilenceAll']:
                    print(" (silence all)", end="")
                if silence['MetricsAlerts']:
                    print(" (silence metrics alerts)", end="")
                if silence['ServiceChecksAlerts']:
                    print(" (silence service checks alerts)", end="")
                if silence['EventAlerts']:
                    print(" (silence event alerts)", end="")
                if silence['BackupAlerts']:
                    print(" (silence backup alerts)", end="")
                if silence['BackupRestoreAlerts']:
                    print(" (silence backup restore alerts)", end="")
                if silence['AuditAlerts']:
                    print(" (silence audit alerts)", end="")
                if silence['AdaptiveRepairAlerts']:
                    print(" (silence adaptive repair alerts)", end="")
                if silence['GenericAlerts']:
                    print(" (silence generic alerts)", end="")
                if silence['GenericTaskAlerts']:
                    print(" (silence generic task alerts)", end="")
                if silence['LogAlerts']:
                    print(" (silence log alerts)", end="")
                if silence['NodeAlerts']:
                    print(" (silence node alerts)", end="")
                if silence['RepairAlerts']:
                    print(" (silence repair alerts)", end="")
                if silence['RollingRestartAlerts']:
                    print(" (silence rolling restart alerts)", end="")
                if silence['ScheduledReportsAlerts']:
                    print(" (silence scheduled reports alerts)", end="")
                if not silence['Active']:
                    print(" (deactivated)", end="")
                print("\n\n")
