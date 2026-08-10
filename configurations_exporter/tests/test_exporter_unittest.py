import os
import tempfile
import unittest
from unittest import mock

import yaml

from src.axonops import AxonOps
from src.exporter import EXPORT_ROOT, Exporter
from src.urls import SECTION_NAMES
from src.utils import ExporterError, HTTPCodeError


class ExporterTestCase(unittest.TestCase):
    def setUp(self):
        self.axonops = AxonOps(org_name="acme", api_token="tok")

    def make_exporter(self, **kwargs):
        kwargs.setdefault("sections", ["alert_rules"])
        return Exporter(self.axonops, org="acme", cluster="prod", **kwargs)


class TestSectionSelection(ExporterTestCase):
    def test_no_sections_means_every_section(self):
        self.assertEqual(self.make_exporter(sections=None).sections, SECTION_NAMES)

    def test_unknown_section_is_rejected(self):
        with self.assertRaises(ExporterError):
            self.make_exporter(sections=["alert_rules", "nope"])


class TestFetch(ExporterTestCase):
    def test_requests_the_cluster_scoped_url_of_each_section(self):
        exporter = self.make_exporter(sections=["alert_rules", "dashboards"])
        with mock.patch.object(self.axonops, "do_request", return_value=[]) as do_request:
            exporter.fetch()

        self.assertEqual(
            [call.args[0] for call in do_request.call_args_list],
            ["/api/v1/alert-rules/acme/cassandra/prod",
             "/api/v1/dashboardtemplate/acme/cassandra/prod?dashver=2.0"])

    def test_cluster_type_is_part_of_the_url(self):
        self.axonops.cluster_type = "kafka"
        with mock.patch.object(self.axonops, "do_request", return_value=[]) as do_request:
            self.make_exporter().fetch()
        self.assertEqual(do_request.call_args.args[0], "/api/v1/alert-rules/acme/kafka/prod")

    def test_payloads_are_keyed_by_section_name(self):
        with mock.patch.object(self.axonops, "do_request", return_value=[{"alert": "CPU"}]):
            self.assertEqual(self.make_exporter().fetch(), {"alert_rules": [{"alert": "CPU"}]})

    def test_a_failing_section_is_skipped_by_default(self):
        exporter = self.make_exporter(sections=["alert_rules", "dashboards"])
        with mock.patch.object(self.axonops, "do_request",
                               side_effect=[HTTPCodeError("boom"), {"dashboards": []}]):
            self.assertEqual(exporter.fetch(), {"dashboards": {"dashboards": []}})

        self.assertEqual(exporter.skipped, ["alert_rules"])

    def test_skipped_sections_are_reset_between_fetches(self):
        exporter = self.make_exporter()
        with mock.patch.object(self.axonops, "do_request", side_effect=HTTPCodeError("boom")):
            exporter.fetch()
        with mock.patch.object(self.axonops, "do_request", return_value=[]):
            exporter.fetch()

        self.assertEqual(exporter.skipped, [])

    def test_ignore_errors_off_aborts_the_export_and_names_the_section(self):
        exporter = self.make_exporter(ignore_errors=False)
        with mock.patch.object(self.axonops, "do_request", side_effect=HTTPCodeError("boom")):
            with self.assertRaises(ExporterError) as raised:
                exporter.fetch()

        self.assertIn("alert_rules", str(raised.exception))


class TestWrite(ExporterTestCase):
    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        cwd = os.getcwd()
        os.chdir(self.tmp.name)
        self.addCleanup(os.chdir, cwd)

    def test_document_carries_the_export_context(self):
        document = self.make_exporter().document({"alert_rules": []})
        self.assertEqual(document["org"], "acme")
        self.assertEqual(document["cluster"], "prod")
        self.assertEqual(document["cluster_type"], "cassandra")
        self.assertEqual(document["configuration"], {"alert_rules": []})

    def test_the_output_directory_is_named_after_the_org_and_cluster(self):
        self.assertEqual(self.make_exporter().output_directory(),
                         os.path.join(EXPORT_ROOT, "acme", "prod"))

    def test_a_cluster_name_that_is_unsafe_as_a_path_is_cleaned_up(self):
        exporter = Exporter(self.axonops, org="acme", cluster="../prod cluster")
        self.assertEqual(exporter.output_directory(),
                         os.path.join(EXPORT_ROOT, "acme", "prod_cluster"))

    def test_one_file_is_written_per_section(self):
        exporter = self.make_exporter()
        exporter.write({"alert_rules": [{"alert": "CPU"}], "dashboards": {}})

        directory = exporter.output_directory()
        self.assertEqual(sorted(os.listdir(directory)),
                         ["alert_rules.yaml", "dashboards.yaml"])

        with open(os.path.join(directory, "alert_rules.yaml"), encoding="utf-8") as handle:
            document = yaml.safe_load(handle)

        self.assertEqual(list(document["configuration"]), ["alert_rules"])
        self.assertEqual(document["configuration"]["alert_rules"], [{"alert": "CPU"}])
        self.assertEqual(document["cluster"], "prod")

    def test_an_existing_export_directory_is_reused(self):
        exporter = self.make_exporter()
        exporter.write({"alert_rules": []})
        exporter.write({"alert_rules": [{"alert": "CPU"}]})

        with open(os.path.join(exporter.output_directory(), "alert_rules.yaml"),
                  encoding="utf-8") as handle:
            document = yaml.safe_load(handle)

        self.assertEqual(document["configuration"]["alert_rules"], [{"alert": "CPU"}])


if __name__ == "__main__":
    unittest.main()
