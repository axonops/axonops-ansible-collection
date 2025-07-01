import json
import urllib.parse
from ansible.module_utils.urls import open_url
from typing import List


class AxonOps:
    cloud_url: str = "https://dash.axonops.cloud"

    def __init__(self, org_name: str, auth_token: str = '', base_url: str = '', username: str = '', password: str = '',
                 cluster_type: str = 'cassandra', api_token: str = '', override_saas: bool = False):
        self.org_name = org_name
        self.auth_token = auth_token
        self.api_token = api_token
        self.username = username
        self.password = password
        self.cluster_type = cluster_type
        self.jwt = ''

        # save the integration output to a var so we can use it multiple times
        self.integrations_output = {}

        # collect the errors, will check it on every module
        self.errors = []

        # set the base url
        if base_url:
            # if saas is overridden, the url will always be treated as saas
            if override_saas:
                self.base_url = base_url.rstrip("/") + "/" + org_name
            else:
                # if saas is not overridden, it is treated as on-prem
                self.base_url = base_url.rstrip("/")

        else:
            # if nothing is specified, it is AxonOps Cloud
            self.base_url = AxonOps.cloud_url + "/" + org_name

        # if you have a username and password, it will be used for the login
        if self.username and self.password:
            self.jwt = self.get_jwt()

    def get_cluster_type(self) -> str:
        """
        getter for cluster_type
        """
        return self.cluster_type

    def get_jwt(self):
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
            if not result or 'token' not in result:
                self.errors.append(f"{self.base_url}/api/login returned an invalid result {result} {return_error}")
                return None
            self.jwt = result['token']
            return self.jwt

    def dash_url(self):
        return self.base_url

    def do_request(self, rel_url: str, method: str = 'GET', ok_codes: List[int] = [200, 201, 204],
                   data: any = None,
                   json_data: any = None,
                   form_field: str = ""):
        """
        Perform a GET request to AxonOps and return the response or an error
        """
        # bearer empty is for anonymous
        bearer = ''

        #
        api_token = ''

        # if we have auth_token, use it
        if self.auth_token:
            bearer = self.auth_token

        # if we have an api token for on prem axonserver instances
        if self.api_token:
            api_token = self.api_token

        # if we have jwt, use it
        if self.jwt:
            bearer = self.jwt

        full_url = self.base_url + '/' + rel_url.lstrip('/')

        if data is None and json_data is not None:
            data = json.dumps(json_data).encode('utf-8')

        headers = {
            'Accept': 'application/json',
            'User-agent': 'AxonOps Ansible Module',
        }

        if bearer:
            headers['Authorization'] = f'Bearer {bearer}'
        if api_token:
            headers['Authorization'] = f'AxonApi {api_token}'
        if form_field != "":
            headers['Content-type'] = 'application/x-www-form-urlencoded'
            data = form_field + "=" + urllib.parse.quote_plus(data)
        elif data is not None:
            headers['Content-type'] = 'application/json'

        res = None
        try:
            with open_url(
                    method=method.upper(),
                    url=full_url,
                    headers=headers,
                    data=data
            ) as res:
                if res.status not in ok_codes:
                    return None, f'{full_url} return code is {res.status}'
                content = res.read()
        except Exception as e:
            return None, str(e) + f" {full_url}"
        finally:
            if res is not None:
                res.close()

        # Not all requests return a response so ignore json decoding errors
        try:
            return json.loads(content), None
        except json.JSONDecodeError:
            return None, None

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
