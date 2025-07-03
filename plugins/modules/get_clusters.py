#!/usr/bin/python


DOCUMENTATION = r'''
---
module: axonops.axonops.get_cluster

short_description: List the clusters.

version_added: "1.0.0"

description: List the clusters for your cluster on AxonOps SaaS.

options:
    base_url:
        description:
            - This represent the base url.
            - Specify this parameter if you are running on-premise.
            - Ignore if you are Running AxonOps SaaS.
        required: false
        type: str
    org:
        description:
            - This is the organisation name in AxonOps Saas.
            - It can be read from the environment variable AXONOPS_ORG.
        required: true
        type: str
    auth_token:
        description:
            - api-token for authenticate to AxonOps SaaS.
            - It can be read from the environment variable AXONOPS_TOKEN.
        required: false
        type: str
    api_token:
        description:
            - api-token to authenticate with AxonOps Server
        required: false
        type: str
    username:
        description:
            - Username for authenticate.
            - It can be read from the environment variable AXONOPS_USERNAME.
        required: false
        type: str
    password:
        description:
            - password for authenticate.
            - It can be read from the environment variable AXONOPS_PASSWORD.
        required: false
        type: str
'''

EXAMPLES = r'''
# List clusters on SaaS`
  - name: list clusters on SaaS
    axonops.axonops.cluster:
      auth_token: '{{ secret }}'
      org: example
    register: cluster

'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.axonops.axonops.plugins.module_utils.axonops import AxonOps
from ansible_collections.axonops.axonops.plugins.module_utils.axonops_utils import make_module_args


def run_module():
    module_args = make_module_args({
    })

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    result = {
        'changed': False,
    }

    axonops = AxonOps(module.params['org'], auth_token=module.params['auth_token'], base_url=module.params['base_url'],
                      username=module.params['username'], password=module.params['password'],
                      api_token=module.params['api_token'],override_saas=module.params['override_saas'])

    if axonops.errors:
        module.fail_json(msg=' '.join(axonops.errors), **result)

    org_url = "/api/v1/orgs"

    org_api_output, return_error = axonops.do_request(org_url)
    if return_error:
        module.fail_json(msg=return_error, **result)

    organizations = org_api_output['children']
    module.debug("#### Orgs ####")
    module.debug(organizations)
    results_unsorted = {}

    for organization in organizations:
        clusters = organization['children']
        module.debug("#### Clusters ####")
        module.debug(clusters)
        for cluster in clusters:
            datacenters = cluster['children']

            for datacenter in datacenters:

                cluster_name = datacenter['name']
                cluster_type = datacenter["type"]

                # create a list of all cluster names for each type
                if cluster_type in results_unsorted:
                    results_unsorted[cluster_type].append(cluster_name)
                else:
                    results_unsorted[cluster_type] = [cluster_name]

    # sort the cluster types alphabetically
    result_sorted = {key: sorted(value) for key, value in results_unsorted.items()}

    result['clusters'] = result_sorted

    module.exit_json(**result)

def main():
    run_module()


if __name__ == '__main__':
    main()
