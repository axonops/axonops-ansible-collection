import unittest
from unittest.mock import patch

from axonopscli.axonops import AxonOps


class TestGetJWT(unittest.TestCase):
    def test_get_jwt_returns_cached_token_without_calling_do_request(self):
        client = AxonOps(org_name="acme", base_url="https://example.com", username="u", password="p")
        client.jwt = "cached-token"

        with patch.object(AxonOps, 'do_request') as mocked_do_request:
            token = client.get_jwt()

        self.assertEqual(token, "cached-token")
        mocked_do_request.assert_not_called()

    def test_get_jwt_calls_do_request_and_caches_token(self):
        client = AxonOps(org_name="acme", base_url="https://example.com", username="u", password="p")
        client.jwt = ""

        def fake_do_request(url, json_data=None, method=None):
            # Validate inputs
            self.assertEqual(url, "/api/login")
            self.assertEqual(method, 'POST')
            self.assertEqual(json_data, {"username": "u", "password": "p"})
            return {"token": "new-token"}, None

        with patch.object(AxonOps, 'do_request', side_effect=fake_do_request):
            token = client.get_jwt()

        self.assertEqual(token, "new-token")
        self.assertEqual(client.jwt, "new-token")
        self.assertEqual(client.errors, [])

    def test_get_jwt_appends_error_if_return_error_present(self):
        client = AxonOps(org_name="acme", base_url="https://example.com", username="u", password="p")
        client.jwt = ""

        with patch.object(AxonOps, 'do_request', return_value=({"token": "t"}, "some-error")):
            token = client.get_jwt()

        self.assertEqual(token, "t")
        self.assertIn("some-error", client.errors)


if __name__ == "__main__":
    unittest.main()
