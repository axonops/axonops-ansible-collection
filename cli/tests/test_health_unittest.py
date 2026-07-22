import io
import types
import unittest
from contextlib import redirect_stdout
from unittest import mock

from axonopscli.health import Health

ORGS_PAYLOAD = {
    'children': [
        {
            'name': 'demo',
            'type': 'org',
            'children': [
                {
                    'name': 'cassandra',
                    'type': 'type',
                    'children': [
                        {'name': 'demo-cluster', 'type': 'cassandra', 'status': 0},
                        {'name': 'bad-cluster', 'type': 'cassandra', 'status': 2},
                        {'name': 'warn-cluster', 'type': 'cassandra', 'status': 1},
                        {'name': 'odd-cluster', 'type': 'cassandra', 'status': 7},
                    ],
                },
            ],
        },
    ],
}

HEALTHY_PAYLOAD = {
    'children': [
        {
            'name': 'demo',
            'children': [
                {
                    'name': 'cassandra',
                    'children': [{'name': 'demo-cluster', 'type': 'cassandra', 'status': 0}],
                },
            ],
        },
    ],
}

NODES_PAYLOAD = [{'host_id': 'b167aca6', 'HostIP': '172.18.0.2'}]


def make_args(**overrides):
    args = dict(v=0, org='demo', cluster='demo-cluster', url=None, token=None,
                username=None, password=None, show_healthy=False, show_orgs=False)
    args.update(overrides)
    return types.SimpleNamespace(**args)


def make_axonops(orgs_payload):
    axonops = mock.Mock()
    axonops.do_request.side_effect = lambda url, method: (
        orgs_payload if url.endswith('/orgs') else NODES_PAYLOAD
    )
    return axonops


def run_health(orgs_payload, **arg_overrides):
    """ Run print_health() and return (returned_value, captured_stdout). """
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        healthy = Health(make_axonops(orgs_payload), make_args(**arg_overrides)).print_health()
    return healthy, buffer.getvalue()


class TestHealth(unittest.TestCase):

    def test_lists_only_unhealthy_clusters_by_default(self):
        healthy, output = run_health(ORGS_PAYLOAD)

        self.assertFalse(healthy)
        self.assertIn("Unhealthy clusters:", output)
        self.assertIn("cassandra/bad-cluster: Error", output)
        self.assertIn("cassandra/warn-cluster: Warning", output)
        self.assertNotIn("demo-cluster", output)

    def test_unrecognised_status_is_reported_as_unknown(self):
        _, output = run_health(ORGS_PAYLOAD)

        self.assertIn("cassandra/odd-cluster: Unknown", output)

    def test_all_healthy_reports_success(self):
        healthy, output = run_health(HEALTHY_PAYLOAD)

        self.assertTrue(healthy)
        self.assertIn("All clusters are healthy", output)
        self.assertNotIn("Unhealthy clusters:", output)

    def test_empty_response_is_not_a_failure(self):
        healthy, output = run_health({})

        self.assertTrue(healthy)
        self.assertIn("No clusters found", output)

    def test_show_healthy_lists_healthy_clusters_and_nodes(self):
        _, output = run_health(ORGS_PAYLOAD, show_healthy=True)

        self.assertIn("Healthy clusters:", output)
        self.assertIn("- demo/cassandra/demo-cluster", output)
        self.assertIn("Nodes:", output)

    def test_show_orgs_lists_org_names(self):
        _, output = run_health(ORGS_PAYLOAD, show_orgs=True)

        self.assertIn("Orgs:", output)
        self.assertIn("- demo", output)

    def test_orgs_are_hidden_unless_requested(self):
        _, output = run_health(ORGS_PAYLOAD)

        self.assertNotIn("Orgs:", output)

    def test_verbose_prints_the_settings_block(self):
        _, output = run_health(ORGS_PAYLOAD, v=1, token='a' * 40)

        self.assertIn("Info from settings:", output)
        self.assertIn("Organization: demo", output)
        self.assertIn("Token: a" + "*" * 39, output)


if __name__ == '__main__':
    unittest.main()
