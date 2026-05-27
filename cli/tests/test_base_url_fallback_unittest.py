import unittest
from unittest.mock import patch

from axonopscli.axonops import AxonOps, HTTPCodeError

DASH = "https://dash.axonops.cloud/flare"
SUBDOMAIN = "https://flare.axonops.cloud/dashboard"


class DummyResponse:
    def __init__(self, status_code, json_payload=None):
        self.status_code = status_code
        self._json = json_payload if json_payload is not None else {}
        # Non-empty text so do_request returns json() rather than {} on success.
        self.text = "{}" if json_payload is None else "non-empty"

    def json(self):
        return self._json


class TestBaseUrlFallback(unittest.TestCase):
    """Cloud SaaS clusters live either on the shared dash host
    (dash.axonops.cloud/<org>) or on a dedicated subdomain
    (<org>.axonops.cloud/dashboard). When no explicit URL is given we try the
    shared host first, fall back to the subdomain on a 404, then lock onto
    whichever shape answered for the rest of the session.
    """

    def test_falls_back_to_subdomain_when_shared_host_404s(self):
        calls = []

        def fake_request(method, url, headers=None, data=None):
            calls.append(url)
            if url.startswith(DASH):
                return DummyResponse(404)
            return DummyResponse(200, {"ok": True})

        with patch("requests.request", side_effect=fake_request):
            client = AxonOps(org_name="flare", api_token="t")
            result = client.do_request("/api/v1/alert-rules/flare/cassandra/pyro")

        self.assertEqual(result, {"ok": True})
        self.assertEqual(calls[0], DASH + "/api/v1/alert-rules/flare/cassandra/pyro")
        self.assertEqual(calls[1], SUBDOMAIN + "/api/v1/alert-rules/flare/cassandra/pyro")

    def test_locks_onto_working_shape_after_first_request(self):
        calls = []

        def fake_request(method, url, headers=None, data=None):
            calls.append(url)
            if url.startswith(DASH):
                return DummyResponse(404)
            return DummyResponse(200, {"ok": True})

        with patch("requests.request", side_effect=fake_request):
            client = AxonOps(org_name="flare", api_token="t")
            client.do_request("/api/v1/alert-rules/flare/cassandra/pyro")
            calls.clear()
            client.do_request("/api/v1/integrations/flare/cassandra/pyro")

        # The shared host is never re-probed once the subdomain has answered.
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0].startswith(SUBDOMAIN))

    def test_uses_shared_host_when_it_works_and_does_not_flip_on_later_404(self):
        calls = []

        def fake_request(method, url, headers=None, data=None):
            calls.append(url)
            if "/exists" in url:
                return DummyResponse(200, {"ok": True})
            return DummyResponse(404)  # genuinely missing resource

        with patch("requests.request", side_effect=fake_request):
            client = AxonOps(org_name="acme", api_token="t")
            client.do_request("/api/v1/exists")  # locks onto shared host
            with self.assertRaises(HTTPCodeError):
                client.do_request("/api/v1/missing")

        # A real 404 after the host is confirmed must not trigger a host flip.
        self.assertFalse(any("acme.axonops.cloud" in u for u in calls))

    def test_explicit_base_url_never_falls_back(self):
        calls = []

        def fake_request(method, url, headers=None, data=None):
            calls.append(url)
            return DummyResponse(404)

        with patch("requests.request", side_effect=fake_request):
            client = AxonOps(org_name="flare",
                             base_url="https://self-hosted.example.com",
                             api_token="t")
            with self.assertRaises(HTTPCodeError):
                client.do_request("/api/v1/alert-rules/flare/cassandra/pyro")

        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0].startswith("https://self-hosted.example.com"))

    def test_non_404_failure_does_not_mask_with_host_flip(self):
        calls = []

        def fake_request(method, url, headers=None, data=None):
            calls.append(url)
            return DummyResponse(401)  # bad token, not a wrong-host signal

        with patch("requests.request", side_effect=fake_request):
            client = AxonOps(org_name="flare", api_token="t")
            with self.assertRaises(HTTPCodeError):
                client.do_request("/api/v1/alert-rules/flare/cassandra/pyro")

        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0].startswith(DASH))


if __name__ == "__main__":
    unittest.main()
