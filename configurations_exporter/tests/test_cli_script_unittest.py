import unittest

from src.cli_script import render_env_file, render_script
from src.clusters import Cluster

CASSANDRA = Cluster("demo", "cassandra", "demo-cluster")

ADAPTIVE_REPAIR = {
    "Ready": True, "Active": True, "GcGraceThreshold": 86400, "SegmentsPerVnode": 1,
    "TableParallelism": 10, "SegmentRetries": 3, "BlacklistedTables": ["ks.big", "ks.old"],
    "FilterTWCSTables": True, "SegmentTargetSizeMB": 0, "MaxSegmentsPerTable": 0,
    "SegmentTimeout": "30m",
}

SCHEDULED_REPAIRS = {
    "Repairs": [],
    "ScheduledRepairs": [{
        "ID": "abc", "Params": [{
            "keyspace": "system_auth", "tables": ["roles"], "blacklistedTables": [],
            "nodes": [], "segmentsPerNode": 4, "segmented": True, "incremental": False,
            "jobThreads": 2, "scheduleExpr": "0 3 * * *", "primaryRange": True,
            "parallelism": "DC-Aware", "optimiseStreams": False,
            "specificDataCenters": ["dc1", "dc2"], "tag": "nightly", "skipPaxos": True,
            "paxosOnly": False,
        }],
    }],
    "AdaptiveScheduledRepairs": None,
}

SILENCES = [
    {"ID": "1", "Duration": "2h", "IsRecurring": True, "CronExpr": "0 1 * * *",
     "SilenceAll": True, "DCs": []},
    {"ID": "2", "Duration": "30m", "IsRecurring": False, "CronExpr": "0 * * * *",
     "SilenceAll": False, "DCs": [{"Name": "dc1"}],
     "MetricsAlerts": True, "NodeAlerts": True, "BackupAlerts": False},
]


class TestEnvFile(unittest.TestCase):
    def test_the_org_is_exported(self):
        self.assertIn("export AXONOPS_ORG=demo", render_env_file("demo"))

    def test_a_given_url_is_exported_and_a_missing_one_is_left_commented(self):
        self.assertIn("export AXONOPS_URL=http://127.0.0.1:3000",
                      render_env_file("demo", url="http://127.0.0.1:3000"))
        self.assertIn("# export AXONOPS_URL=http://127.0.0.1:3000", render_env_file("demo"))

    def test_the_cluster_is_only_written_when_one_was_named(self):
        self.assertIn("export AXONOPS_CLUSTER=prod", render_env_file("demo", cluster="prod"))
        self.assertNotIn("AXONOPS_CLUSTER", render_env_file("demo"))

    def test_a_given_username_is_exported(self):
        self.assertIn("export AXONOPS_USERNAME=admin", render_env_file("demo", username="admin"))

    def test_no_credential_value_is_ever_written(self):
        """The token and the password stay commented placeholders."""
        rendered = render_env_file("demo", url="https://dash.axonops.cloud", username="admin")
        self.assertIn("# export AXONOPS_TOKEN=", rendered)
        self.assertIn("# export AXONOPS_PASSWORD=", rendered)
        for line in rendered.splitlines():
            if line.startswith("export "):
                self.assertNotIn("TOKEN", line)
                self.assertNotIn("PASSWORD", line)

    def test_values_needing_it_are_quoted(self):
        self.assertIn("export AXONOPS_ORG='my org'", render_env_file("my org"))


class ScriptTestCase(unittest.TestCase):
    def render(self, configuration, cluster=CASSANDRA, org="demo"):
        self.script = render_script(org, [(cluster, configuration)])
        return self.script

    def commands(self):
        return [line for line in self.script.splitlines() if line.startswith("$AXONOPS_CLI")]


class TestScriptShape(ScriptTestCase):
    def test_it_is_a_bash_script_naming_the_org(self):
        script = self.render({})
        self.assertTrue(script.startswith("#!/usr/bin/env bash"))
        self.assertIn("org 'demo'", script)
        self.assertIn("set -euo pipefail", script)

    def test_the_cli_to_drive_is_overridable(self):
        self.assertIn('AXONOPS_CLI="${AXONOPS_CLI:-python3 axonops.py}"', self.render({}))

    def test_every_cluster_gets_its_own_block(self):
        script = render_script("demo", [(CASSANDRA, {}),
                                        (Cluster("demo", "kafka", "demo-kafka"), {})])
        self.assertIn("### cluster demo-cluster (cassandra)", script)
        self.assertIn("### cluster demo-kafka (kafka)", script)

    def test_sections_without_a_cli_command_are_listed_as_a_todo(self):
        script = self.render({"alert_rules": [], "dashboards": {}, "adaptive_repair": {}})
        self.assertIn("#   - alert_rules", script)
        self.assertIn("#   - dashboards", script)
        self.assertNotIn("#   - adaptive_repair", script)

    def test_a_section_with_nothing_to_replay_says_so(self):
        self.assertIn("# nothing to set for silences", self.render({"silences": []}))


class TestAdaptiveRepair(ScriptTestCase):
    def test_the_settings_become_one_repair_command(self):
        self.render({"adaptive_repair": ADAPTIVE_REPAIR})
        self.assertEqual(self.commands(), [
            "$AXONOPS_CLI --cluster demo-cluster repair --enabled --gcgrace 86400 "
            "--tableparallelism 10 --maxsegmentspertable 0 --segmentretries 3 "
            "--segmenttargetsizemb 0 --excludedtables ks.big,ks.old "
            "--excludetwcstables true --segmenttimeout 30m"
        ])

    def test_an_inactive_repair_is_disabled(self):
        self.render({"adaptive_repair": dict(ADAPTIVE_REPAIR, Active=False)})
        self.assertIn("repair --disabled", self.commands()[0])

    def test_an_unset_segment_timeout_is_left_out(self):
        self.render({"adaptive_repair": dict(ADAPTIVE_REPAIR, SegmentTimeout="0s")})
        self.assertNotIn("--segmenttimeout", self.commands()[0])

    def test_no_excluded_tables_means_no_flag(self):
        self.render({"adaptive_repair": dict(ADAPTIVE_REPAIR, BlacklistedTables=None)})
        self.assertNotIn("--excludedtables", self.commands()[0])


class TestScheduledRepairs(ScriptTestCase):
    def test_each_scheduled_repair_becomes_a_command(self):
        self.render({"scheduled_repairs": SCHEDULED_REPAIRS})
        command = self.commands()[0]

        self.assertIn("--cluster demo-cluster scheduledrepair", command)
        self.assertIn("--keyspace system_auth", command)
        self.assertIn("--tables roles", command)
        self.assertIn("--datacenters dc1,dc2", command)
        self.assertIn("--segmentspernode 4", command)
        self.assertIn("--jobthreads 2", command)
        self.assertIn("--scheduleexpr '0 3 * * *'", command)
        self.assertIn("--parallelism DC-Aware", command)
        self.assertIn("--tags nightly", command)
        self.assertIn("--segmented", command)
        self.assertIn("--partitionerrange", command)
        self.assertIn("--skippaxos", command)
        self.assertNotIn("--incremental", command)
        self.assertNotIn("--paxosonly", command)
        self.assertNotIn("--excludedtables", command)

    def test_a_cluster_without_scheduled_repairs_yields_no_command(self):
        self.render({"scheduled_repairs": {"Repairs": [], "ScheduledRepairs": None}})
        self.assertEqual(self.commands(), [])


class TestSilences(ScriptTestCase):
    def test_each_silence_becomes_a_create_command(self):
        self.render({"silences": SILENCES})
        self.assertEqual(len(self.commands()), 2)

    def test_a_recurring_silence_keeps_its_cron_expression(self):
        self.render({"silences": SILENCES})
        self.assertIn("silence --create --duration 2h --cronexpr '0 1 * * *'", self.commands()[0])

    def test_silence_all_names_no_alert_type(self):
        self.render({"silences": SILENCES})
        self.assertNotIn("--silence", self.commands()[0].split("silence --create")[1])

    def test_a_targeted_silence_names_its_alert_types_and_dcs(self):
        self.render({"silences": SILENCES})
        command = self.commands()[1]

        self.assertIn("--silencemetricsalerts", command)
        self.assertIn("--silencenodealerts", command)
        self.assertNotIn("--silencebackupalerts", command)
        self.assertIn('--dcs \'[{"Name": "dc1"}]\'', command)
        self.assertNotIn("--cronexpr", command)


if __name__ == "__main__":
    unittest.main()
