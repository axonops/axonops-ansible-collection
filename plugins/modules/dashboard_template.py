#!/usr/bin/python


DOCUMENTATION = r'''
---
module: axonops_dashboard_template

short_description: Set the dashboard templates.

version_added: "1.0.0"

description: Set the dashboard for your cluster on AxonOps Cloud or On-Prem.

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
    cluster:
        description:
            - Cluster where to apply.
            - It can be read from the environment variable AXONOPS_CLUSTER.
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
    cluster_type:
        description:
            - The typo of cluster, cassandra, DSE, etc.
            - Default is cassandra
            - It can be read from the environment variable AXONOPS_CLUSTER_TYPE.
        required: false
        type: str
'''

import uuid
from ansible.module_utils.basic import AnsibleModule
from copy import copy

from ansible_collections.axonops.axonops.plugins.module_utils.axonops import AxonOps
from ansible_collections.axonops.axonops.plugins.module_utils.axonops_utils import dicts_are_different, \
    make_module_args


def run_module():
    module_args = make_module_args({
        'present': {'type': 'bool', 'required': False, 'default': True},
        'name': {'type': 'str', 'required': True},
        'filters': {'type': 'list', 'required': False},
        'panels': {'type': 'list', 'required': False},
    })

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    result = {
        'changed': False,
    }

    axonops = AxonOps(module.params['org'], auth_token=module.params['auth_token'], base_url=module.params['base_url'],
                      username=module.params['username'], password=module.params['password'],
                      cluster_type=module.params['cluster_type'], api_token=module.params['api_token'],
                      override_saas=module.params['override_saas'])

    if axonops.errors:
        module.fail_json(msg=' '.join(axonops.errors), **result)

    # e.g  http://127.0.0.1:3000/api/v1/dashboardtemplate/demo/cassandra/demo-cluster
    dashboardtemplate_url = (f"/api/v1/dashboardtemplate/"
                             f"{module.params['org']}/{axonops.get_cluster_type()}/{module.params['cluster']}?dashver=2.0")

    old_templates, return_error = axonops.do_request(dashboardtemplate_url)
    if return_error:
        module.fail_json(msg=return_error, **result)

    # the old template if exists
    old_template_found = None
    # the position where we found the old template
    old_template_position = None
    dashboards_to_send = []
    if 'dashboards' in old_templates:
        for i, old_template in enumerate(old_templates['dashboards']):
            if 'name' in old_template and old_template['name'] == module.params['name']:
                old_template_found = old_template
                old_template_position = i
            else:
                dashboards_to_send.append(old_template)

    if old_template_found:
        old_data = {
            'present': True,
            'name': old_template_found['name'],
            'filters': old_template_found['filters'],
            'panels': old_template_found['panels'],
        }
    else:
        old_data = {
            'present': False,
        }

    new_data = {
        'present': module.params['present'],
        'name': module.params['name'],
        'filters': module.params['filters'],
        'panels': module.params['panels'],
    }

    changed = dicts_are_different(new_data, old_data)
    result['changed'] = changed
    result['diff'] = {'before': old_data, 'after': new_data}

    if module.check_mode or not changed:
        module.exit_json(**result)
        return

    result['test'] = len(old_templates['dashboards'])
    # if we have the position of the old index, we use it to keep the order
    if old_template_position:
        dashboards_to_send.insert(old_template_position, new_data)
    else:
        dashboards_to_send.append(new_data)
    payload = {
        'type': module.params['cluster_type'],
        'dashboards': dashboards_to_send
    }

    # result['payload'] = {'payload': payload}
    _, error = axonops.do_request(rel_url=dashboardtemplate_url, method='PUT', json_data=payload)
    if error is not None:
        module.fail_json(msg="Failed to create dashboard: " + str(error), **result)
        return

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
