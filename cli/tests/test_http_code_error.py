import unittest
from unittest.mock import patch

from axonopscli.axonops import AxonOps, HTTPCodeError


class DummyResponse:
    def __init__(self, status_code: int, json_payload=None):
        self.status_code = status_code
        self._json_payload = json_payload if json_payload is not None else {}

    def json(self):
        return self._json_payload


class TestHTTPCodeError(unittest.TestCase):
    def test_do_request_raises_http_code_error_for_non_ok_status(self):
        # Arrange
        def fake_request(method, url, headers=None, data=None):
            return DummyResponse(status_code=500)

        with patch("requests.request", side_effect=fake_request):
            client = AxonOps(org_name="acme", base_url="https://example.com")

            # Act + Assert
            with self.assertRaises(HTTPCodeError) as ctx:
                client.do_request("/api/test")

            self.assertIn("https://example.com/api/test", str(ctx.exception))
            self.assertIn("500", str(ctx.exception))

    def test_do_request_respects_custom_ok_codes_and_raises_when_not_included(self):
        # Arrange: 200 but ok_codes excludes 200 → should raise
        def fake_request(method, url, headers=None, data=None):
            return DummyResponse(status_code=200, json_payload={"ok": True})

        with patch("requests.request", side_effect=fake_request):
            client = AxonOps(org_name="acme", base_url="https://example.com")

            # Act + Assert
            with self.assertRaises(HTTPCodeError) as ctx:
                client.do_request("/api/test", ok_codes=[201])

            self.assertIn("https://example.com/api/test", str(ctx.exception))
            self.assertIn("200", str(ctx.exception))



if __name__ == "__main__":
    unittest.main()
