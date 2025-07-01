#!/usr/bin/python


DOCUMENTATION = r'''
---
module: axonops.axonops.adaptive_repair

short_description: Set the Adaptive Repair.

version_added: "1.0.0"

description: Set the Adaptive Repair for your cluster on AxonOps SaaS.

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
    active:
        description:
            - Set the state of the Adaptive Repair.
            - The default is TRUE.
        required: false
        type: bool
    gc_grace:
        description:
            - The GC Grace Threshold to take in consideration.
            - The default is 86400.
        required: false
        type: int
    segments:
        description:
            - The number of segments per Vnode.
            - The default is 1.
        required: false
        type: int
    parallelism:
        description:
            - Table Parallelism. How many tables will be repaired at the same time.
            - The default is 10.
        required: false
        type: int
    blacklisted:
        description:
            - The table to exclude.
            - the default is [].
        required: false
        type: list
    filter_twcs:
        description:
            - If set to true it will ignore TWCS tables.
            - The default is TRUE.
        required: false
        type: bool
    retries: 3
        description:
            - The maximum number retries before fail a segment
            - The default is 3
        required: false
        type: int

'''

EXAMPLES = r'''
# Activate Adaptive Repair on cluster `my_cluster` of `my_company`
  - name: Activate Adaptive Repair on my_cluster
    axonops.axonops.adaptive_repair:
      auth_token: "{{ secret }}"
      org: my_company
      cluster: my_cluster
      active: true
# Make sure single_instance has no Adaptive Repair active
  - name: Make sure single_instance has no Adaptive Repair active
    axonops.axonops.daptive_repair:
      auth_token: "{{ secret }}"
      org: my_company
      cluster: single_instance
      active: false

'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.axonops.axonops.plugins.module_utils.axonops import AxonOps
from ansible_collections.axonops.axonops.plugins.module_utils.axonops_utils import make_module_args, \
    dicts_are_different


def run_module():
    module_args = make_module_args({
        'active': {'type': 'bool', 'default': True},
        'gc_grace': {'type': 'int', 'required': False, 'default': '86400'},
        'segments': {'type': 'int', 'required': False},
        'parallelism': {'type': 'int', 'required': False, 'default': '10'},
        'blacklisted': {'type': 'list', 'required': False, 'default': []},
        'filter_twcs': {'type': 'bool', 'required': False, 'default': True},
        'retries': {'type': 'int', 'required': False, 'default': '3'},
        'segment_target_size_mb': {'type': 'int', 'required': False}
    })

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
        mutually_exclusive=[
            ('segments', 'segment_target_size_mb'),
        ]
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

    adaptive_repair_url = \
        f"/api/v1/adaptiveRepair/{module.params['org']}/{axonops.get_cluster_type()}/{module.params['cluster']}"

    saas_settings, return_error = axonops.do_request(adaptive_repair_url)
    if return_error:
        module.fail_json(msg=return_error, **result)

    current_setting = {
        'active': saas_settings['Active'],
        'gc_grace': saas_settings['GcGraceThreshold'],
        'blacklisted': saas_settings['BlacklistedTables'],
        'filter_twcs': saas_settings['FilterTWCSTables'],
        'retries': saas_settings['SegmentRetries'],
        'parallelism': saas_settings['TableParallelism']
    }

    if 'SegmentsPerVnode' in saas_settings and saas_settings['SegmentsPerVnode']:
        current_setting['segments'] = saas_settings['SegmentsPerVnode']
    if 'SegmentTargetSizeMB' in saas_settings and saas_settings['SegmentTargetSizeMB']:
        current_setting['segment_target_size_mb'] = saas_settings['SegmentTargetSizeMB']

    requested_setting = {
        'active': module.params['active'],
        'gc_grace': module.params['gc_grace'],
        'blacklisted': module.params['blacklisted'],
        'filter_twcs': module.params['filter_twcs'],
        'retries': module.params['retries'],
        'parallelism': module.params['parallelism']
    }

    if 'segments' in module.params and module.params['segments']:
        requested_setting['segments'] = module.params['segments']
    if 'segment_target_size_mb' in module.params and module.params['segment_target_size_mb']:
        requested_setting['segment_target_size_mb'] = module.params['segment_target_size_mb']

    payload = {
        'Active': requested_setting['active'],
        'GcGraceThreshold': requested_setting['gc_grace'],
        'TableParallelism': requested_setting['parallelism'],
        'BlacklistedTables': requested_setting['blacklisted'],
        'FilterTWCSTables': requested_setting['filter_twcs'],
        'SegmentRetries': requested_setting['retries']
    }

    if 'segments' in requested_setting and requested_setting['segments']:
        payload['SegmentsPerVnode'] = requested_setting['segments']
    if 'segment_target_size_mb' in requested_setting and requested_setting['segment_target_size_mb']:
        payload['SegmentTargetSizeMB'] = requested_setting['segment_target_size_mb']

    changed = dicts_are_different(current_setting, requested_setting)
    result['diff'] = {'before': current_setting, 'after': requested_setting}
    result['changed'] = changed

    if module.check_mode or not changed:
        module.exit_json(**result)
        return

    _, return_error = axonops.do_request(
        rel_url=adaptive_repair_url,
        method='POST',
        json_data=payload,
    )

    if return_error:
        module.fail_json(msg=return_error, **result)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
