import json
import urllib.parse
from typing import List

import requests


class HTTPCodeError(Exception):
    pass


class AxonOps:

    def __init__(self, org_name: str, base_url: str = '', username: str = '', password: str = '',
                 cluster_type: str = 'cassandra', api_token: str = '', verbose=False):
        self.org_name = org_name
        self.api_token = api_token
        self.username = username
        self.password = password
        self.cluster_type = cluster_type
        self.jwt = ''
        self.verbose = verbose

        # save the integration output to a var so we can use it multiple times
        self.integrations_output = {}

        # collect the errors, will check it on every module
        self.errors = []

        # clean the base url or use the default
        if not base_url:
            self.base_url = f'https://dash.axonops.cloud/{org_name}'
        else:
            # If base_url is defined then its most likely a standalone axonserver instance which doesn't need /{org_name}
            # for axonsaas dev environment can still set the org_name in the base_url env var
            self.base_url = f'{base_url.rstrip("/")}'

        # if you have username and password, it will be used as login
        if self.username and self.password:
            self.jwt = self.get_jwt()

    def get_cluster_type(self) -> str:
        """
        getter for cluster_type
        """
        return self.cluster_type

    def dash_url(self):
        return self.base_url

    def get_jwt(self) -> str:
        """
        Get the JWT from the login endpoint
        """
        # if you have it already, use it
        if self.jwt:
            return self.jwt
        else:
            json_data = {
                "username": self.username,
                "password": self.password
            }

            result, return_error = self.do_request("/api/login", json_data=json_data, method='POST')

            if return_error:
                self.errors.append(return_error)
            self.jwt = result['token']
            return self.jwt

    def do_request(self, url: str,
                   method: str = "GET",
                   json_data: any = None,
                   data: any = None,
                   form_field: str = "",
                   ok_codes: List[int] = [200, 201, 204]
                   ) -> dict:
        """
        Do HTTP(S) requests for the other methods.

        Parameters:
            url (str): The relative URL after the base and the org name.
            method (str): HTTP method to use for the request (GET, POST, PUT, DELETE, etc.)
        """
        full_url = f'{self.dash_url()}{url}'

        # Select the bearer if it is necessary
        bearer = ''

        # If we have user and password, use them
        if self.username and self.password:
            bearer = self.do_login()

        # If we have a token, use it
        if self.api_token:
            bearer = self.api_token

        if data is None and json_data is not None:
            data = json.dumps(json_data).encode('utf-8')

        headers = {
            'Accept': 'application/json',
            'Authorization': f'Bearer {bearer}',
            'User-agent': 'AxonOps Python Module'
        }

        if form_field != "":
            headers['Content-type'] = 'application/x-www-form-urlencoded'
            data = form_field + "=" + urllib.parse.quote_plus(data)
        elif data is not None:
            headers['Content-type'] = 'application/json'

        method = method.upper()
        if self.verbose:
            print(f"{method} {full_url} {headers}")

        try:
            response = requests.request(method, full_url, headers=headers, data=data)
            if response.status_code == 204:
                if self.verbose:
                    print(f"204 No Content received from {full_url}")
                return {}

            if response.status_code not in ok_codes:
                raise HTTPCodeError(f"Call to {full_url} returned {response.status_code}")
            return response.json()
        except json.decoder.JSONDecodeError:
            print(f"url: {full_url} header: {headers} return: {response.status_code}")
            raise

    def get_integration_output(self, cluster: str):
        """
        get the integration output from local variable if present, or from API
        """
        # if we don't have already the integration API output, call the API
        if cluster not in self.integrations_output:
            integrations, error = self.do_request(
                f"/api/v1/integrations/{self.org_name}/{self.get_cluster_type()}/{cluster}")
            if error is not None:
                return None, error

            # save the integration output for the next time
            self.integrations_output[cluster] = integrations
        return self.integrations_output[cluster], None

    def find_integration_by_name_and_type(self, cluster, integration_type, name):
        """
        get the integration by the name and type
        """
        # Get the list of current integrations
        integrations, error = self.get_integration_output(cluster)
        if error is not None:
            return None, error

        definitions = integrations['Definitions'] if 'Definitions' in integrations else []

        # Check if the named integration already exists
        if definitions:
            for definition in definitions:
                if 'Type' in definition and 'Params' in definition and 'name' in definition['Params'] \
                        and definition['Type'] == integration_type and definition['Params']['name'] == name:
                    return definition, None

        return None, None

    def find_integration_id_by_name(self, cluster, name):
        """
        get the integration by the name
        """
        # Get the list of current integrations
        integrations, error = self.get_integration_output(cluster)
        if error is not None:
            return None, error

        definitions = integrations['Definitions'] if 'Definitions' in integrations else []

        # Check if the named integration already exists
        if definitions:
            for definition in definitions:
                if 'Params' in definition and 'name' in definition['Params'] and definition['Params']['name'] == name:
                    return definition["ID"], None

        return None, None

    def find_integration_name_by_id(self, cluster, integration_id):
        """
        get the integration by the ID
        """
        # Get the list of current integrations
        integrations, error = self.get_integration_output(cluster)
        if error is not None:
            return None, error

        definitions = integrations['Definitions'] if 'Definitions' in integrations else []

        # find the definition
        if definitions:
            for definition in definitions:
                if definition["ID"] == integration_id:
                    return definition['Params']['name'], None

        return None, None

    def find_nodes_ids(self, nodes, org, cluster):
        nodes_returned, error = self.do_request(f"api/v1/nodes/{org}/{self.get_cluster_type()}/{cluster}")
        if error is not None:
            return None, error

        list_of_ids = []

        for node in nodes:
            for node_returned in nodes_returned:
                details = node_returned['Details']
                if node == details['human_readable_identifier'] or node == node_returned['HostIP']:
                    list_of_ids.append(node_returned['host_id'])
                    break

        return list_of_ids, None


if __name__ == "__main__":
    print("This file is not meant to be run directly. This file only contains object that other scripts are using.")
