import json
import unittest
from types import SimpleNamespace
from unittest import mock

from src.axonops import AxonOps
from src.urls import LOGIN_URL
from src.utils import APIConnectionError, HTTPCodeError


def response(status_code=200, body=None, text=None):
    if text is None:
        text = "" if body is None else json.dumps(body)
    return SimpleNamespace(status_code=status_code, text=text, json=lambda: json.loads(text))


class TestAxonOpsBasics(unittest.TestCase):
    def test_get_cluster_type_default(self):
        client = AxonOps(org_name="acme")
        self.assertEqual(client.get_cluster_type(), "cassandra")

    def test_get_cluster_type_custom(self):
        client = AxonOps(org_name="acme", cluster_type="kafka")
        self.assertEqual(client.get_cluster_type(), "kafka")

    def test_dash_url_default_uses_org_name(self):
        client = AxonOps(org_name="acme")
        self.assertEqual(client.dash_url(), "https://dash.axonops.cloud/acme")

    def test_dash_url_uses_given_base_url_and_strips_trailing_slash(self):
        client = AxonOps(org_name="acme", base_url="https://example.com/")
        self.assertEqual(client.dash_url(), "https://example.com")


class TestBearer(unittest.TestCase):
    def test_api_token_wins_over_username_and_password(self):
        client = AxonOps(org_name="acme", api_token="tok", username="u", password="p")
        self.assertEqual(client.bearer("/api/v1/orgs"), "tok")

    def test_login_request_is_never_authenticated(self):
        client = AxonOps(org_name="acme", username="u", password="p")
        self.assertEqual(client.bearer(LOGIN_URL), "")

    def test_username_and_password_are_exchanged_for_a_jwt(self):
        client = AxonOps(org_name="acme", username="u", password="p")
        with mock.patch.object(client, "do_request", return_value={"token": "jwt"}) as do_request:
            self.assertEqual(client.bearer("/api/v1/orgs"), "jwt")
            do_request.assert_called_once()

    def test_no_credentials_means_no_bearer(self):
        client = AxonOps(org_name="acme")
        self.assertEqual(client.bearer("/api/v1/orgs"), "")


class TestGetJWT(unittest.TestCase):
    def test_token_is_cached_after_the_first_login(self):
        client = AxonOps(org_name="acme", username="u", password="p")
        with mock.patch.object(client, "do_request", return_value={"token": "jwt"}) as do_request:
            self.assertEqual(client.get_jwt(), "jwt")
            self.assertEqual(client.get_jwt(), "jwt")
            self.assertEqual(do_request.call_count, 1)

    def test_login_without_a_token_in_the_response_raises(self):
        client = AxonOps(org_name="acme", username="u", password="p")
        with mock.patch.object(client, "do_request", return_value={}):
            with self.assertRaises(HTTPCodeError):
                client.get_jwt()


class TestDoRequest(unittest.TestCase):
    def setUp(self):
        self.client = AxonOps(org_name="acme", api_token="tok")

    def test_returns_the_decoded_body(self):
        with mock.patch("src.axonops.requests.request",
                        return_value=response(body={"a": 1})) as request:
            self.assertEqual(self.client.do_request("/api/v1/orgs"), {"a": 1})
        request.assert_called_once()
        self.assertEqual(request.call_args.args[1], "https://dash.axonops.cloud/acme/api/v1/orgs")
        self.assertEqual(request.call_args.kwargs["headers"]["Authorization"], "Bearer tok")

    def test_no_credentials_sends_no_authorization_header(self):
        client = AxonOps(org_name="acme", base_url="http://127.0.0.1:3000")
        with mock.patch("src.axonops.requests.request", return_value=response(body={})) as request:
            client.do_request("/api/v1/orgs")
        self.assertNotIn("Authorization", request.call_args.kwargs["headers"])

    def test_no_content_returns_an_empty_dict(self):
        with mock.patch("src.axonops.requests.request", return_value=response(status_code=204)):
            self.assertEqual(self.client.do_request("/api/v1/orgs"), {})

    def test_empty_body_returns_an_empty_dict(self):
        with mock.patch("src.axonops.requests.request", return_value=response(text="   ")):
            self.assertEqual(self.client.do_request("/api/v1/orgs"), {})

    def test_unexpected_status_code_raises(self):
        with mock.patch("src.axonops.requests.request",
                        return_value=response(status_code=403, text="forbidden")):
            with self.assertRaises(HTTPCodeError):
                self.client.do_request("/api/v1/orgs")

    def test_an_unreachable_server_raises_a_connection_error(self):
        import requests

        with mock.patch("src.axonops.requests.request",
                        side_effect=requests.exceptions.ConnectionError("refused")):
            with self.assertRaises(APIConnectionError):
                self.client.do_request("/api/v1/orgs")

    def test_non_json_body_raises(self):
        with mock.patch("src.axonops.requests.request", return_value=response(text="<html>")):
            with self.assertRaises(HTTPCodeError):
                self.client.do_request("/api/v1/orgs")

    def test_json_payload_is_serialised_with_a_content_type(self):
        with mock.patch("src.axonops.requests.request", return_value=response(body={})) as request:
            self.client.do_request("/api/v1/orgs", method="post", json_data={"k": "v"})
        self.assertEqual(request.call_args.args[0], "POST")
        self.assertEqual(request.call_args.kwargs["data"], b'{"k": "v"}')
        self.assertEqual(request.call_args.kwargs["headers"]["Content-type"], "application/json")


if __name__ == "__main__":
    unittest.main()
