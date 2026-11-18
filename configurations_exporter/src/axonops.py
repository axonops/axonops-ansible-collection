"""HTTP client for the AxonOps API."""

import json
from typing import Any, List, Optional

import requests

from .urls import LOGIN_URL
from .utils import APIConnectionError, HTTPCodeError

# Cluster type assumed when neither the command line nor the orgs tree names one.
DEFAULT_CLUSTER_TYPE = 'cassandra'


class AxonOps:
    """Minimal read-oriented client for the AxonOps API.

    Base URL resolution follows the same rules as the AxonOps Ansible modules:
      * no ``base_url`` -> AxonOps Cloud, ``https://dash.axonops.cloud/{org}``
        (the org is part of the path)
      * explicit ``base_url`` -> self-hosted axon-server, the org is *not*
        appended and instead travels in the request path of each endpoint.
    """

    def __init__(self, org_name: str, base_url: str = '', username: str = '', password: str = '',
                 cluster_type: str = DEFAULT_CLUSTER_TYPE, api_token: str = '', verbose: int = 0,
                 timeout: int = 30):
        self.org_name = org_name
        self.api_token = api_token
        self.username = username
        self.password = password
        self.cluster_type = cluster_type
        self.verbose = verbose
        self.timeout = timeout
        self.jwt = ''

        if not base_url:
            self.base_url = f'https://dash.axonops.cloud/{org_name}'
        else:
            self.base_url = base_url.rstrip('/')

    def get_cluster_type(self) -> str:
        """Getter for cluster_type."""
        return self.cluster_type

    def dash_url(self) -> str:
        """Base URL every relative endpoint is appended to."""
        return self.base_url

    def get_jwt(self) -> str:
        """Log in with username/password and cache the returned JWT."""
        if self.jwt:
            return self.jwt

        json_data = {
            "username": self.username,
            "password": self.password,
        }
        result = self.do_request(LOGIN_URL, json_data=json_data, method='POST')

        token = result.get('token') if isinstance(result, dict) else None
        if not token:
            raise HTTPCodeError(f"Login to {self.dash_url()}{LOGIN_URL} did not return a token")

        self.jwt = token
        return self.jwt

    def bearer(self, url: str) -> str:
        """Resolve the bearer token to use for a request.

        An API token always wins; otherwise username/password are exchanged for
        a JWT. The login request itself is never authenticated.
        """
        if self.api_token:
            return self.api_token
        if url != LOGIN_URL and self.username and self.password:
            return self.get_jwt()
        return ''

    def do_request(self, url: str,
                   method: str = "GET",
                   json_data: Any = None,
                   data: Any = None,
                   ok_codes: Optional[List[int]] = None) -> Any:
        """Perform an HTTP(S) request against the AxonOps API.

        Parameters:
            url: relative URL, starting with a leading slash.
            method: HTTP method to use.
            json_data: payload to serialise as a JSON body.
            data: raw body, takes precedence over ``json_data``.
            ok_codes: status codes treated as success.

        Returns the decoded JSON body, or ``{}`` for an empty response.
        Raises ``HTTPCodeError`` on any other status code.
        """
        if ok_codes is None:
            ok_codes = [200, 201, 204]

        full_url = f'{self.dash_url()}{url}'

        if data is None and json_data is not None:
            data = json.dumps(json_data).encode('utf-8')

        headers = {
            'Accept': 'application/json',
            'User-agent': 'AxonOps Configurations Exporter',
        }

        # Nothing to send when the server has authentication disabled.
        bearer = self.bearer(url)
        if bearer:
            headers['Authorization'] = f'Bearer {bearer}'

        if data is not None:
            headers['Content-type'] = 'application/json'

        method = method.upper()
        if self.verbose:
            print(f"{method} {full_url}")

        try:
            response = requests.request(method, full_url, headers=headers, data=data,
                                        timeout=self.timeout)
        except requests.exceptions.RequestException as exc:
            raise APIConnectionError(f"Could not reach {full_url}: {exc}") from exc

        if response.status_code not in ok_codes:
            raise HTTPCodeError(f"Call to {full_url} returned {response.status_code}: {response.text[:200]}")

        if response.status_code == 204 or not response.text.strip():
            return {}

        try:
            return response.json()
        except json.decoder.JSONDecodeError as exc:
            raise HTTPCodeError(f"Call to {full_url} returned a non-JSON body: {response.text[:200]}") from exc


if __name__ == "__main__":
    print("This file is not meant to be run directly. It only contains objects other scripts use.")
