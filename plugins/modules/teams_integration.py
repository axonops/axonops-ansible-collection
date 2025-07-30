#!/usr/bin/python3

DOCUMENTATION = r'''
---
module: axonops_teams_integration

short_description: Configure a Microsoft Teams integration for AxonOps

version_added: '1.0.0'

description: Configure a Microsoft Teams integration for AxonOps

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
            - Cluster where to apply the Adaptive Repair.
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
TODO

'''

EXAMPLES = r'''
TODO
'''

RETURN = r'''
TODO
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.axonops.axonops.plugins.module_utils.axonops import AxonOps
from ansible_collections.axonops.axonops.plugins.module_utils.axonops_utils import make_module_args, \
    dicts_are_different


def run_module():
    module_args = make_module_args({
        'name': {'type': 'str', 'required': True},
        'webhook_url': {'type': 'str'},
        'present': {'type': 'bool', 'default': True},
    })

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
        required_if=[('present', True, ('webhook_url',))]
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

    integrations_url = (f"/api/v1/integrations/"
                        f"{module.params['org']}/{axonops.get_cluster_type()}/{module.params['cluster']}")

    # Find the existing integration
    found_definition, error = axonops.find_integration_by_name_and_type(module.params['cluster'], 'microsoft_teams', module.params['name'])
    if error is not None:
        module.fail_json(msg=error)
        return

    existing_id = found_definition['ID'] if found_definition and 'ID' in found_definition else None

    if existing_id:
        old_data = {
            'name': found_definition['Params']['name'],
            'webhook_url': found_definition['Params']['webHookURL'],
            'present': True,
        }
    else:
        old_data = {'present': False}

    if module.params['present']:
        new_data = {
            'name': module.params['name'],
            'webhook_url': module.params['webhook_url'],
            'present': module.params['present'],
        }
    else:
        new_data = {
            'name': '',
            'webhook_url': '',
            'present': False,
        }

    # Work out what changes are required and make the diff
    if not module.params['present'] and not existing_id:
        changed = False
    else:
        changed = dicts_are_different(new_data, old_data)
    result['changed'] = changed
    result['diff'] = {'before': old_data, 'after': new_data}

    # Exit if in check mode or no changes
    if module.check_mode or not changed:
        module.exit_json(**result)
        return

    # Delete the existing integration
    if existing_id and not module.params['present']:
        res, error = axonops.do_request(
            rel_url=integrations_url + "/" + existing_id,
            method='DELETE'
        )
        if error is not None:
            module.fail_json(msg=error)
            return
        module.exit_json(**result)

    # Add or update the integration
    payload = {
        'type': 'microsoft_teams',
        'params': {
            'name': new_data['name'],
            'webHookURL': new_data['webhook_url'],
        }
    }
    if existing_id:
        payload['id'] = existing_id

    _, error = axonops.do_request(
        rel_url=integrations_url,
        method='POST',
        json_data=payload
    )
    if error is not None:
        module.fail_json(msg=error)
        return

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
