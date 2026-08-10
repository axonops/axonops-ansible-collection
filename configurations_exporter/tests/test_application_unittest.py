import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest import mock

from src.application import Application
from src.clusters import Cluster
from src.urls import SECTION_NAMES


def run(argv, env=None):
    """Run the CLI with a controlled environment and return its exit code."""
    with mock.patch.dict("os.environ", env or {}, clear=True):
        return Application().run(argv)


class ApplicationTestCase(unittest.TestCase):
    """Runs each test in a temporary directory — an export writes to the cwd."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name

        cwd = os.getcwd()
        os.chdir(self.tmp)
        self.addCleanup(os.chdir, cwd)


class TestArgumentHandling(ApplicationTestCase):
    def test_no_command_prints_the_help_and_fails(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = run([])
        self.assertEqual(exit_code, 1)
        self.assertIn("usage:", buffer.getvalue())

    def test_sections_lists_every_exportable_section(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            exit_code = run(["sections"])
        self.assertEqual(exit_code, 0)
        self.assertEqual(buffer.getvalue().split(), SECTION_NAMES)

    def test_the_org_is_mandatory(self):
        self.assertEqual(run(["--token", "tok", "export"]), 1)

    def test_credentials_are_optional(self):
        """A self-hosted server may have authentication disabled."""
        with mock.patch("src.application.Exporter"):
            self.assertEqual(
                run(["--org", "acme", "--cluster", "prod",
                     "--url", "http://127.0.0.1:3000", "export"]), 0)

    def test_options_default_to_the_axonops_environment_variables(self):
        env = {
            "AXONOPS_ORG": "acme",
            "AXONOPS_CLUSTER": "prod",
            "AXONOPS_CLUSTER_TYPE": "kafka",
            "AXONOPS_TOKEN": "tok",
            "AXONOPS_URL": "https://axonops.internal/",
        }
        with mock.patch.dict("os.environ", env, clear=True):
            application = Application()
            with mock.patch("src.application.Exporter") as exporter:
                exit_code = application.run(["export"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(application.axonops.dash_url(), "https://axonops.internal")
        self.assertEqual(application.axonops.get_cluster_type(), "kafka")
        self.assertEqual(application.axonops.api_token, "tok")
        self.assertEqual(exporter.call_args.kwargs["org"], "acme")
        self.assertEqual(exporter.call_args.kwargs["cluster"], "prod")

    def test_flags_win_over_the_environment(self):
        env = {"AXONOPS_ORG": "from-env", "AXONOPS_CLUSTER": "from-env", "AXONOPS_TOKEN": "tok"}
        with mock.patch.dict("os.environ", env, clear=True):
            application = Application()
            with mock.patch("src.application.Exporter") as exporter:
                application.run(["--org", "acme", "--cluster", "prod", "export"])

        self.assertEqual(exporter.call_args.kwargs["org"], "acme")
        self.assertEqual(exporter.call_args.kwargs["cluster"], "prod")


class TestClusterSelection(ApplicationTestCase):
    """Without --cluster the export covers every cluster of the org."""

    base_argv = ["--org", "demo", "--url", "http://127.0.0.1:3000"]

    def test_a_named_cluster_is_exported_on_its_own(self):
        with mock.patch("src.application.discover_clusters") as discover, \
                mock.patch("src.application.Exporter") as exporter:
            exit_code = run(self.base_argv + ["--cluster", "prod", "export"])

        self.assertEqual(exit_code, 0)
        discover.assert_not_called()
        self.assertEqual(exporter.call_count, 1)
        self.assertEqual(exporter.call_args.kwargs["cluster"], "prod")
        self.assertEqual(exporter.call_args.kwargs["cluster_type"], "cassandra")

    def test_a_named_cluster_keeps_the_given_cluster_type(self):
        with mock.patch("src.application.Exporter") as exporter:
            run(self.base_argv + ["--cluster", "prod", "--cluster-type", "dse", "export"])
        self.assertEqual(exporter.call_args.kwargs["cluster_type"], "dse")

    def test_without_a_cluster_every_discovered_cluster_is_exported(self):
        discovered = [Cluster("demo", "cassandra", "demo-cluster"),
                      Cluster("demo", "kafka", "demo-kafka")]

        with mock.patch("src.application.discover_clusters", return_value=discovered) as discover, \
                mock.patch("src.application.Exporter") as exporter:
            exit_code = run(self.base_argv + ["export"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(discover.call_args.kwargs, {"org": "demo"})
        self.assertEqual(
            [(call.kwargs["cluster"], call.kwargs["cluster_type"])
             for call in exporter.call_args_list],
            [("demo-cluster", "cassandra"), ("demo-kafka", "kafka")])
        self.assertEqual(exporter.return_value.write.call_count, 2)

    def test_a_discovered_cluster_keeps_its_own_type_over_the_default(self):
        """--cluster-type describes --cluster; discovery uses what the API reports."""
        with mock.patch("src.application.discover_clusters",
                        return_value=[Cluster("demo", "kafka", "demo-kafka")]), \
                mock.patch("src.application.Exporter") as exporter:
            run(self.base_argv + ["export"])

        self.assertEqual(exporter.call_args.kwargs["cluster_type"], "kafka")

    def test_an_org_without_clusters_is_an_error(self):
        with mock.patch("src.application.discover_clusters", return_value=[]):
            self.assertEqual(run(self.base_argv + ["export"]), 1)


class TestExportCommand(ApplicationTestCase):
    base_argv = ["--org", "acme", "--cluster", "prod", "--token", "tok", "export"]

    def test_export_options_reach_the_exporter(self):
        with mock.patch("src.application.Exporter") as exporter:
            exit_code = run(self.base_argv + ["--section", "alert_rules", "--section", "dashboards"])

        self.assertEqual(exit_code, 0)
        self.assertEqual(exporter.call_args.kwargs["sections"], ["alert_rules", "dashboards"])
        exporter.return_value.write.assert_called_once_with(exporter.return_value.fetch.return_value)

    def test_failing_sections_are_skipped_by_default(self):
        with mock.patch("src.application.Exporter") as exporter:
            run(self.base_argv)
        self.assertTrue(exporter.call_args.kwargs["ignore_errors"])

    def test_fail_on_error_makes_the_export_strict(self):
        with mock.patch("src.application.Exporter") as exporter:
            run(self.base_argv + ["--fail-on-error"])
        self.assertFalse(exporter.call_args.kwargs["ignore_errors"])

    def test_an_api_failure_is_reported_as_a_non_zero_exit(self):
        from src.utils import HTTPCodeError

        with mock.patch("src.application.Exporter") as exporter:
            exporter.return_value.fetch.side_effect = HTTPCodeError("boom")
            self.assertEqual(run(self.base_argv), 1)

    def test_an_unknown_section_is_reported_as_a_non_zero_exit(self):
        self.assertEqual(run(self.base_argv + ["--section", "nope"]), 1)


class TestCliSettings(ApplicationTestCase):
    """Every export also leaves the CLI settings next to the YAML."""

    base_argv = ["--org", "acme", "--url", "http://127.0.0.1:3000"]

    def export(self, argv):
        with mock.patch("src.application.Exporter") as exporter:
            exporter.return_value.fetch.return_value = {"adaptive_repair": {"Active": True}}
            self.assertEqual(run(self.base_argv + argv), 0)

    def test_both_files_land_in_the_org_directory(self):
        self.export(["--cluster", "prod", "export"])

        self.assertEqual(sorted(os.listdir(os.path.join(self.tmp, "exports", "acme"))),
                         [".env.axonops", "acme.sh"])

    def test_the_env_file_carries_the_connection_settings(self):
        self.export(["--cluster", "prod", "--username", "admin", "export"])

        with open(os.path.join(self.tmp, "exports", "acme", ".env.axonops"),
                  encoding="utf-8") as handle:
            content = handle.read()

        self.assertIn("export AXONOPS_ORG=acme", content)
        self.assertIn("export AXONOPS_CLUSTER=prod", content)
        self.assertIn("export AXONOPS_URL=http://127.0.0.1:3000", content)
        self.assertIn("export AXONOPS_USERNAME=admin", content)

    def test_the_token_is_never_written_to_disk(self):
        with mock.patch("src.application.Exporter"):
            run(["--org", "acme", "--cluster", "prod", "--token", "sup3r-s3cret",
                 "--password", "hunter2", "export"])

        with open(os.path.join(self.tmp, "exports", "acme", ".env.axonops"),
                  encoding="utf-8") as handle:
            content = handle.read()

        self.assertNotIn("sup3r-s3cret", content)
        self.assertNotIn("hunter2", content)

    def test_the_script_covers_every_exported_cluster(self):
        discovered = [Cluster("acme", "cassandra", "prod"), Cluster("acme", "kafka", "events")]
        with mock.patch("src.application.discover_clusters", return_value=discovered), \
                mock.patch("src.application.Exporter") as exporter:
            exporter.return_value.fetch.return_value = {"adaptive_repair": {"Active": True}}
            run(self.base_argv + ["export"])

        with open(os.path.join(self.tmp, "exports", "acme", "acme.sh"), encoding="utf-8") as handle:
            script = handle.read()

        self.assertIn("### cluster prod (cassandra)", script)
        self.assertIn("### cluster events (kafka)", script)
        self.assertIn("$AXONOPS_CLI --cluster prod repair --enabled", script)


if __name__ == "__main__":
    unittest.main()
