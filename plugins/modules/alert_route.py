#!/usr/bin/python3

DOCUMENTATION = r'''
---
module: axonops.axonops.alert_route

short_description: Configure an alerting route for AxonOps

version_added: '1.0.0'

description: Configure an alerting route for AxonOps SaaS

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
        type: srt
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
    present:
        description:
            - Set the state of the Alert Route.
            - The default is TRUE.
        required: false
        type: bool
    type:
        description:
            - Type of the route.
        required: true
        choices: [ global, metrics, backups, servicechecks, nodes, commands, repairs, rollingrestart ]
        type: str
    severity:
        description:
            - Severity of the route.
        required: true
        choices: [ info, warning, error ]
        type: str
    integration_type:
        description:
            - Type of the integration.
            - email, smtp, pagerduty, slack, teams, servicenow, webhook, opsgenie
        type: str
    integration_name:
        description:
            - Name of the integration.
            - This is used to identify the integration in AxonOps.
        type: str
    enable_override:
        description:
            - Allow the integration to be overridden
        required: false
        type: bool

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

# Type name mapping Ansible => AxonOps
types_map = {
    'global': 'Global',
    'metrics': 'Metrics',
    'backups': 'Backups',
    'servicechecks': 'Service%20Checks',
    'nodes': 'Nodes',
    'commands': 'Commands',
    'repairs': 'Repairs',
    'rollingrestart': 'Rolling%20Restart'
}


def run_module():
    module_args = make_module_args({
        'type': {'type': 'str', 'required': True, 'choices': types_map.keys()},
        'severity': {'type': 'str', 'required': True, 'choices': ['info', 'warning', 'error']},
        'integration_type': {'type': 'str'},
        'integration_name': {'type': 'str'},
        'enable_override': {'type': 'bool', 'required': False, 'default': True},
        'present': {'type': 'bool', 'default': True},
    })

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
        required_together=[
            ('integration_type', 'integration_name'),
        ],
    )
    result = {
        'changed': False,
    }

    org = module.params['org']
    cluster = module.params['cluster']

    axonops = AxonOps(module.params['org'], auth_token=module.params['auth_token'], base_url=module.params['base_url'],
                      username=module.params['username'], password=module.params['password'],
                      cluster_type=module.params['cluster_type'], api_token=module.params['api_token'],
                      override_saas=module.params['override_saas'])

    if axonops.errors:
        module.fail_json(msg=' '.join(axonops.errors), **result)

    integrations, error = axonops.do_request(f"/api/v1/integrations/{org}/{axonops.get_cluster_type()}/{cluster}")
    if error is not None:
        module.fail_json(msg=error)
        return

    routings = integrations['Routings'] if integrations and 'Routings' in integrations else []

    integration, error = axonops.find_integration_by_name_and_type(
        cluster, module.params['integration_type'], module.params['integration_name'])
    if error is not None:
        module.fail_json(msg=error)
        return

    # if you have a type and a name as input
    integration_id = None
    if module.params['integration_type'] and module.params['integration_name']:
        if integration is None or 'ID' not in integration:
            module.fail_json(
                msg=f"The integration of type {module.params['integration_type']} with name "
                    f"{module.params['integration_name']} was not found in AxonOps")
            return

        integration_id = integration['ID']

    # See if this route is already configured
    is_global = module.params['type'] == 'global'
    exists = False
    old_override_enabled = False
    override_property = 'Override' + module.params['severity'].title()
    axon_type = types_map[module.params['type']]
    for routing in routings:
        if 'Type' in routing and routing['Type'] == axon_type and 'Routing' in routing:
            if override_property in routing:
                old_override_enabled = routing[override_property]

                # if it is only a override and it is set, set as exists
                if not module.params['integration_name']:
                    exists = True
            for entry in routing['Routing'] or []:
                if 'Severity' in entry and 'ID' in entry \
                        and entry['Severity'] == module.params['severity'] and integration_id \
                        and entry['ID'] == integration_id:
                    exists = True
                    break

    old_data = {
        'type': module.params['type'],
        'severity': module.params['severity'],
        'integration_type': module.params['integration_type'] or "",
        'integration_name': module.params['integration_name'] or "",
        'present': exists,
    }
    new_data = {
        'type': module.params['type'],
        'severity': module.params['severity'],
        'integration_type': module.params['integration_type'] or "",
        'integration_name': module.params['integration_name'] or "",
        'present': module.params['present'],
    }

    if not is_global:
        old_data['enable_override'] = old_override_enabled
        new_data['enable_override'] = module.params['enable_override']

    # Work out what changes are required and make the diff
    changed = dicts_are_different(new_data, old_data)
    result['changed'] = changed
    result['diff'] = {'before': old_data, 'after': new_data}

    # Exit if in check mode or no changes
    if module.check_mode or not changed:
        module.exit_json(**result)
        return

    # Change the override setting
    if not is_global and old_data['enable_override'] != new_data['enable_override']:
        _, error = axonops.do_request(
            rel_url=f"api/v1/integrations-override/"
                    f"{org}/{axonops.get_cluster_type()}/{cluster}/{axon_type}/{module.params['severity']}",
            method='PUT',
            json_data={'value': new_data['enable_override']}
        )
        if error is not None:
            module.fail_json(msg=error)
            return

    # Add or delete the route if required
    if old_data['present'] != new_data['present']:
        _, error = axonops.do_request(
            rel_url=f"api/v1/integrations-routing/"
                    f"{org}/{axonops.get_cluster_type()}/{cluster}/{axon_type}/{module.params['severity']}/{integration_id}",
            method='POST' if module.params['present'] else 'DELETE'
        )
        if error is not None:
            module.fail_json(msg=error)
            return

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
