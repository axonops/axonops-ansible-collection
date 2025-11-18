import unittest

from axonopscli.axonops import AxonOps


class TestAxonOpsBasics(unittest.TestCase):
    def test_get_cluster_type_default(self):
        client = AxonOps(org_name="acme")
        self.assertEqual(client.get_cluster_type(), "cassandra")

    def test_get_cluster_type_custom(self):
        client = AxonOps(org_name="acme", cluster_type="scylla")
        self.assertEqual(client.get_cluster_type(), "scylla")

    def test_dash_url_default_uses_org_name(self):
        client = AxonOps(org_name="acme")
        self.assertEqual(client.dash_url(), "https://dash.axonops.cloud/acme")

    def test_dash_url_uses_given_base_url_and_strips_trailing_slash(self):
        client = AxonOps(org_name="acme", base_url="https://example.com/")
        self.assertEqual(client.dash_url(), "https://example.com")


if __name__ == "__main__":
    unittest.main()



