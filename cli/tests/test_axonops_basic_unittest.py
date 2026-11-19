import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from axonopscli.axonops import AxonOps, _scrub_auth_headers


class TestScrubAuthHeaders(unittest.TestCase):
    def test_masks_bearer_token(self):
        result = _scrub_auth_headers({"Authorization": "Bearer super-secret-xyz"})
        self.assertEqual(result["Authorization"], "Bearer ***")

    def test_masks_axonapi_token(self):
        result = _scrub_auth_headers({"Authorization": "AxonApi super-secret-xyz"})
        self.assertEqual(result["Authorization"], "AxonApi ***")

    def test_passes_through_when_no_auth(self):
        result = _scrub_auth_headers({"Accept": "application/json"})
        self.assertEqual(result, {"Accept": "application/json"})

    def test_does_not_mutate_input(self):
        original = {"Authorization": "Bearer xyz"}
        _scrub_auth_headers(original)
        self.assertEqual(original["Authorization"], "Bearer xyz")

    def test_empty_or_none(self):
        self.assertEqual(_scrub_auth_headers(None), None)
        self.assertEqual(_scrub_auth_headers({}), {})


class TestVerboseDoesNotLeakToken(unittest.TestCase):
    """Regression: axonops.py:~111 used to print the full headers dict including
    the Bearer token when verbose was set. Ensure it's masked."""

    def test_do_request_verbose_masks_authorization(self):
        class FakeResponse:
            status_code = 200
            text = '{"ok": true}'
            def json(self): return {"ok": True}

        client = AxonOps(org_name="acme", api_token="super-secret-sentinel", verbose=True)
        buf = io.StringIO()
        with patch("requests.request", return_value=FakeResponse()):
            with redirect_stdout(buf):
                client.do_request("/api/v1/test")
        out = buf.getvalue()
        self.assertNotIn("super-secret-sentinel", out,
                         f"token leaked to stdout in verbose mode:\n{out}")
        # Scheme should still appear for debugging context
        self.assertIn("Bearer", out)


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
