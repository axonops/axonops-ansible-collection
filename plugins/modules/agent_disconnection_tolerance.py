#!/usr/bin/python


DOCUMENTATION = r'''
---
module: axonops.axonops.agent_disconnection_tolerance

short_description: Set the Agent Disconnection Tolerance.

version_added: "1.0.0"

description: Set the Agent Disconnection Tolerance on AxonOps SaaS.

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
    warn_timeout:
        description:
            - Set the threshold limit for the warning alert timeout.
        required: false
        type: str
    error_timeout:
        description:
            - Set the threshold limit for the error alert timeout.
        required: false
        type: str
'''

EXAMPLES = r'''
  - name: Set the agent disconnection tolerance to 3 minutes error 2 warning
    axonops.axonops.agent_disconnection_tolerance:
      auth_token: "{{ secret }}"
      org: my_company
      cluster: my_cluster
      error_timeout: 3m
      warn_timeout: 1m
  - name: Set the agent disconnection tolerance to 2 minutes error
    axonops.axonops.agent_disconnection_tolerance:
      auth_token: "{{ secret }}"
      org: my_company
      cluster: my_cluster
      error_timeout: 3m


'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.axonops.axonops.plugins.module_utils.axonops import AxonOps
from ansible_collections.axonops.axonops.plugins.module_utils.axonops_utils import make_module_args, \
    dicts_are_different


def run_module():
    module_args = make_module_args({
        'warn_timeout': {'type': 'str', 'required': True},
        'error_timeout': {'type': 'str', 'required': True}
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

    agent_disconnection_tolerance_url = \
        (f"/api/v1/configs/agentDisconnectionTolerance/"
         f"{module.params['org']}/{axonops.get_cluster_type()}/{module.params['cluster']}")

    saas_settings, return_error = axonops.do_request(agent_disconnection_tolerance_url)
    if return_error:
        module.fail_json(msg=return_error, **result)

    current_setting = {
        'warn_timeout': saas_settings['warn_timeout'],
        'error_timeout': saas_settings['error_timeout'],
    }
    requested_setting = {
        'warn_timeout': module.params['warn_timeout'],
        'error_timeout': module.params['error_timeout'],
    }
    payload = {
        'warn_timeout': requested_setting['warn_timeout'],
        'error_timeout': requested_setting['error_timeout'],
    }

    changed = dicts_are_different(current_setting, requested_setting)
    result['diff'] = {'before': current_setting, 'after': requested_setting}
    result['changed'] = changed

    if module.check_mode or not changed:
        module.exit_json(**result)
        return

    _, return_error = axonops.do_request(
        rel_url=agent_disconnection_tolerance_url,
        method='PUT',
        json_data=payload,
    )

    if return_error:
        module.fail_json(msg=return_error, **result)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
