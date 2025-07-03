
DOCUMENTATION = r'''
---
module:

short_description: Set the shell checks.

version_added: "1.0.0"

description: Set the Shell Checks for your cluster on AxonOps SaaS.

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

EXAMPLES = r'''
# Activate Adaptive Repair on cluster `my_cluster` of `my_company`
  - name: Activate Adaptive Repair on my_cluster
    axonops_adaptive_repair:
      auth_token: "{{ secret }}"
      org: my_company
      cluster: my_cluster
      present: true
# Make sure single_instance has no Adaptive Repair present
  - name: Make sure single_instance has no Adaptive Repair present
    axonops_adaptive_repair:
      auth_token: "{{ secret }}"
      org: my_company
      cluster: single_instance
      present: false

'''

RETURN = r'''
url:
    description: The endpoint url.
    type: str
    returned: always

'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.axonops.axonops.plugins.module_utils.axonops import AxonOps
from ansible_collections.axonops.axonops.plugins.module_utils.axonops_utils import make_module_args, \
    dicts_are_different


def run_module():
    module_args = make_module_args({
        'present': {'type': 'bool', 'default': True},
        'id': {'type': 'str', 'required': True,
               'choices': ['axon_agent_ip', 'axon_agent_hostname', 'env_hostname', 'comp_listen_address']},
    })

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    result = dict(
        changed=False,
    )

    axonops = AxonOps(module.params['org'], auth_token=module.params['auth_token'], base_url=module.params['base_url'],
                      username=module.params['username'], password=module.params['password'],
                      cluster_type=module.params['cluster_type'], api_token=module.params['api_token'],
                      override_saas=module.params['override_saas'])

    if axonops.errors:
        module.fail_json(msg=' '.join(axonops.errors), **result)

    setting_url = \
        f"/api/v1/clusterSettings/{module.params['org']}/{axonops.get_cluster_type()}/{module.params['cluster']}"
    humanreadableid_url = \
        f"/api/v1/humanReadableId/{module.params['org']}/{axonops.get_cluster_type()}/{module.params['cluster']}"

    cluster_setting, return_error = axonops.do_request(setting_url)
    if return_error:
        module.fail_json(msg=return_error, **result)

    old_data = {
        'id': cluster_setting['HumanReadableID']
    }

    new_data = {
        'id': module.params['id']
    }

    changed = dicts_are_different(new_data, old_data)
    result['changed'] = changed
    result['diff'] = {'before': old_data, 'after': new_data}

    # Exit if in check mode or no changes
    if module.check_mode or not changed:
        module.exit_json(**result)
        return

    _, error = axonops.do_request(
        rel_url=humanreadableid_url,
        method='PUT',
        json_data={'HumanReadableID': module.params['id']},
    )
    if error is not None:
        module.fail_json(msg=error)
        return

    module.exit_json(**result)
    return


def main():
    run_module()


if __name__ == '__main__':
    main()
