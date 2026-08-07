import unittest
from unittest import mock

from src.axonops import AxonOps
from src.clusters import Cluster, discover_clusters

# The shape `/api/v1/orgs` answers with: org -> type -> cluster.
ORGS_TREE = {
    "children": [
        {"name": "demo", "type": "org", "children": [
            {"name": "cassandra", "type": "type", "children": [
                {"name": "demo-cluster", "type": "cassandra", "status": 0},
                {"name": "other-cluster", "type": "cassandra", "status": 1},
            ]},
            {"name": "kafka", "type": "type", "children": [
                {"name": "demo-kafka", "type": "kafka", "status": 0},
            ]},
        ]},
        {"name": "acme", "type": "org", "children": [
            {"name": "cassandra", "type": "type", "children": [
                {"name": "acme-cluster", "type": "cassandra", "status": 0},
            ]},
        ]},
    ]
}


class TestDiscoverClusters(unittest.TestCase):
    def setUp(self):
        self.axonops = AxonOps(org_name="demo", base_url="http://127.0.0.1:3000")

    def discover(self, tree=None, **kwargs):
        tree = ORGS_TREE if tree is None else tree
        with mock.patch.object(self.axonops, "do_request", return_value=tree) as do_request:
            clusters = discover_clusters(self.axonops, **kwargs)
        self.request = do_request
        return clusters

    def test_reads_the_orgs_endpoint(self):
        self.discover()
        self.request.assert_called_once_with("/api/v1/orgs")

    def test_flattens_every_org_type_and_cluster(self):
        self.assertEqual(self.discover(), [
            Cluster("demo", "cassandra", "demo-cluster"),
            Cluster("demo", "cassandra", "other-cluster"),
            Cluster("demo", "kafka", "demo-kafka"),
            Cluster("acme", "cassandra", "acme-cluster"),
        ])

    def test_org_narrows_the_result(self):
        self.assertEqual([cluster.name for cluster in self.discover(org="acme")],
                         ["acme-cluster"])

    def test_every_cluster_keeps_the_type_the_api_reports(self):
        self.assertEqual([(cluster.name, cluster.cluster_type)
                          for cluster in self.discover(org="demo")],
                         [("demo-cluster", "cassandra"), ("other-cluster", "cassandra"),
                          ("demo-kafka", "kafka")])

    def test_an_unknown_org_finds_nothing(self):
        self.assertEqual(self.discover(org="nope"), [])

    def test_the_type_falls_back_to_the_name_of_the_type_node(self):
        tree = {"children": [{"name": "demo", "children": [
            {"name": "cassandra", "children": [{"name": "demo-cluster"}]}]}]}
        self.assertEqual(self.discover(tree), [Cluster("demo", "cassandra", "demo-cluster")])

    def test_an_empty_tree_finds_nothing(self):
        self.assertEqual(self.discover({}), [])
        self.assertEqual(self.discover({"children": None}), [])


if __name__ == "__main__":
    unittest.main()
