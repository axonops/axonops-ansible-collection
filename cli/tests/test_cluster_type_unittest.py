import io
import types
import unittest
from contextlib import redirect_stderr
from unittest import mock

from axonopscli.application import Application
from axonopscli.components.dashboard import Dashboard
from axonopscli.components.nodes import Nodes
from axonopscli.components.repair import AdaptiveRepair
from axonopscli.components.scheduled_repair import ScheduledRepair
from axonopscli.components.silence import Silence


def make_args(**overrides):
    args = dict(v=0, org='demo', cluster='demo-cluster', cluster_type='dse',
                url=None, token=None, username=None, password=None)
    args.update(overrides)
    return types.SimpleNamespace(**args)


def make_axonops():
    axonops = mock.Mock()
    axonops.do_request.return_value = {}
    return axonops


class TestClusterTypePropagation(unittest.TestCase):
    """ Every component's full_url must use args.cluster_type instead of a hardcoded 'cassandra'. """

    def test_nodes_url_uses_cluster_type(self):
        nodes = Nodes(make_axonops(), make_args())
        self.assertEqual(nodes.full_url, "/api/v1/nodes/demo/dse/demo-cluster")

    def test_nodes_url_defaults_to_cassandra(self):
        nodes = Nodes(make_axonops(), make_args(cluster_type='cassandra'))
        self.assertEqual(nodes.full_url, "/api/v1/nodes/demo/cassandra/demo-cluster")

    def test_nodes_url_supports_kafka(self):
        nodes = Nodes(make_axonops(), make_args(cluster_type='kafka'))
        self.assertEqual(nodes.full_url, "/api/v1/nodes/demo/kafka/demo-cluster")

    def test_adaptive_repair_url_uses_cluster_type(self):
        repair = AdaptiveRepair(make_args(), make_axonops())
        self.assertEqual(repair.full_url, "/api/v1/adaptiveRepair/demo/dse/demo-cluster")

    def test_scheduled_repair_urls_use_cluster_type(self):
        scheduled_repair = ScheduledRepair(make_axonops(), make_args())
        self.assertEqual(scheduled_repair.full_add_repair_url, "/api/v1/addrepair/demo/dse/demo-cluster")
        self.assertEqual(scheduled_repair.full_repair_url, "/api/v1/repair/demo/dse/demo-cluster")
        self.assertEqual(scheduled_repair.full_cassandrascheduledrepair_url,
                         "/api/v1/cassandrascheduledrepair/demo/dse/demo-cluster")

    def test_silence_url_uses_cluster_type(self):
        silence = Silence(make_axonops(), make_args())
        self.assertEqual(silence.full_url, "/api/v1/silenceWindow/demo/dse/demo-cluster")

    def test_dashboard_url_uses_cluster_type(self):
        dashboard = Dashboard(make_axonops(), make_args())
        self.assertEqual(dashboard.full_dashboard_url,
                         "/api/v1/dashboardtemplate/demo/dse/demo-cluster?dashver=2.0")

    def test_dashboard_delete_payload_uses_cluster_type(self):
        axonops = make_axonops()
        dashboard = Dashboard(axonops, make_args())
        dashboard.dashboard_data = [{'name': 'Table'}]

        dashboard.delete_dashboard('Table')

        _, kwargs = axonops.do_request.call_args
        self.assertEqual(kwargs['json_data']['type'], 'dse')


class TestGetAxonopsUsesClusterTypeNotClusterName(unittest.TestCase):
    """ Regression test: get_axonops() must forward args.cluster_type, not args.cluster
    (the cluster name), into AxonOps(cluster_type=...). """

    def test_get_axonops_forwards_cluster_type(self):
        app = Application()
        args = make_args(cluster_type='kafka', cluster='demo-cluster', token='t')

        axonops = app.get_axonops(args)

        self.assertEqual(axonops.get_cluster_type(), 'kafka')
        self.assertNotEqual(axonops.get_cluster_type(), args.cluster)


class TestClusterTypeArgparseDefault(unittest.TestCase):

    def test_cluster_type_defaults_to_cassandra(self):
        app = Application()
        captured = {}

        def fake_run_health(args):
            captured['args'] = args

        app.run_health = fake_run_health
        app.run(['--org', 'demo', '--cluster', 'demo-cluster', 'health'])

        self.assertEqual(captured['args'].cluster_type, 'cassandra')

    def test_cluster_type_flag_overrides_default(self):
        app = Application()
        captured = {}

        def fake_run_health(args):
            captured['args'] = args

        app.run_health = fake_run_health
        app.run(['--org', 'demo', '--cluster', 'demo-cluster', '--cluster-type', 'dse', 'health'])

        self.assertEqual(captured['args'].cluster_type, 'dse')

    def test_cluster_type_rejects_invalid_value(self):
        app = Application()

        with self.assertRaises(SystemExit) as ctx, redirect_stderr(io.StringIO()) as stderr:
            app.run(['--org', 'demo', '--cluster', 'demo-cluster', '--cluster-type', 'scylla', 'health'])

        self.assertEqual(ctx.exception.code, 2)
        self.assertIn('invalid choice', stderr.getvalue())


if __name__ == '__main__':
    unittest.main()
