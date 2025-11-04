#!/usr/bin/python
from typing import Any, Dict

DOCUMENTATION = r'''
---
module: axonops.axonops.adaptive_repair

short_description: Manage Adaptive Repair settings via AxonOps API

version_added: "1.0.0"

description: Configure Adaptive Repair settings for a cluster using the AxonOps API.

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
            - AxonOps will not repair any tables with gc_grace shorter than the specified.
            - The default is 86400.
        required: false
        type: int
    tableparallelism:
        description:
            - Table Parallelism. How many tables will be repaired at the same time.
            - The default is 10.
        required: false
        type: int
    excludedtables:
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
    segmentretries: 3
        description:
            - The maximum number segmentretries before fail a segment
            - The default is 3
        required: false
        type: int
    segmenttargetsizemb:
        description:
            - The target size in MB for each segment.
            - The default is 0 (let AxonOps decide the best size).
        required: false
        type: int
    segmenttimeout:
        description:
            - The timeout for each segment.
            - The default is 2h.
        required: false
        type: str
    maxsegmentspertable:
        description:
            - The maximum number of segments per table.
            - The default is 0 (let AxonOps decide the best number).
        required: false


'''

EXAMPLES = r'''
- name: Ensure adaptive repair is enabled with specific settings
  adaptive_repair:
    org: my-org
    cluster: my-cluster
    active: true
    maxsegmentspertable: 4
    excludedtables: []
    filter_twcs: false
    segmentretries: 3
    tableparallelism: 2
    gc_grace: 86400
    segmenttargetsizemb: 64
    override_saas: false

- name: Disable adaptive repair
  adaptive_repair:
    org: my-org
    cluster: my-cluster
    active: false

'''

RETURN = r'''
changed:
  description: Whether the module made changes.
  type: bool
  returned: always
current_setting:
  description: The current settings fetched from the API (mapped to module option names).
  type: dict
  returned: when success
original_setting:
  description: The requested settings assembled from module parameters (mapped to module option names).
  type: dict
  returned: when success
api_response:
  description: Raw response (decoded JSON) from the API — useful for debugging.
  type: dict
  returned: when success
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.axonops.axonops.plugins.module_utils.axonops import AxonOps
from ansible_collections.axonops.axonops.plugins.module_utils.axonops_utils import make_module_args, \
    dicts_are_different


def run_module():
    module_args = make_module_args({
        'active': {'type': 'bool', 'default': True},
        'excludedtables': {'type': 'list', 'required': False, 'default': []},
        'filter_twcs': {'type': 'bool', 'required': False, 'default': True},
        'gc_grace': {'type': 'int', 'required': False, 'default': '86400'},
        'maxsegmentspertable': {'type': 'int', 'required': False, 'default': 0},
        'segmentretries': {'type': 'int', 'required': False, 'default': 3},
        'segmenttargetsizemb': {'type': 'int', 'required': False, 'default': 0},
        'segmenttimeout': {'type': 'str', 'required': False, 'default': '2h'},
        'tableparallelism': {'type': 'int', 'required': False, 'default': 10},
    })

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True
    )

    result: Dict[str, Any] = {
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

    if not saas_settings or not isinstance(saas_settings, dict) or 'Active' not in saas_settings:
        module.fail_json(msg='Adaptive Repair settings not found for the cluster.', **result)

    current_setting = {
        'active': saas_settings['Active'],
        'excludedtables': saas_settings['BlacklistedTables'] if saas_settings['BlacklistedTables'] is not None else [],
        'filter_twcs': saas_settings['FilterTWCSTables'],
        'gc_grace': saas_settings['GcGraceThreshold'],
        'maxsegmentspertable': saas_settings['MaxSegmentsPerTable'],
        'segmentretries': saas_settings['SegmentRetries'],
        'segmenttargetsizemb': saas_settings['SegmentTargetSizeMB'],
        'segmenttimeout': saas_settings['SegmentTimeout'],
        'tableparallelism': saas_settings['TableParallelism'],
    }

    requested_setting = {
        'active': module.params['active'],
        'excludedtables': module.params['excludedtables'],
        'filter_twcs': module.params['filter_twcs'],
        'gc_grace': module.params['gc_grace'],
        'maxsegmentspertable': module.params['maxsegmentspertable'],
        'segmentretries': module.params['segmentretries'],
        'segmenttargetsizemb': module.params['segmenttargetsizemb'],
        'segmenttimeout': module.params['segmenttimeout'],
        'tableparallelism': module.params['tableparallelism'],
    }

    payload = {
        'Active': requested_setting['active'],
        'BlacklistedTables': requested_setting['excludedtables'],
        'FilterTWCSTables': requested_setting['filter_twcs'],
        'GcGraceThreshold': requested_setting['gc_grace'],
        'MaxSegmentsPerTable': requested_setting['maxsegmentspertable'],
        'SegmentRetries': requested_setting['segmentretries'],
        'SegmentTargetSizeMB': requested_setting['segmenttargetsizemb'],
        'SegmentTimeout': requested_setting['segmenttimeout'],
        'TableParallelism': requested_setting['tableparallelism'],
    }

    result['payload'] = payload
    result['current_setting'] = current_setting
    result['requested_setting'] = requested_setting
    result['saas_settings_original'] = saas_settings

    changed = dicts_are_different(current_setting, requested_setting)
    result['diff'] = {'before': current_setting, 'after': requested_setting}
    result['changed'] = changed

    if module.check_mode or not changed:
        module.exit_json(**result)

    _, return_error = axonops.do_request(
        rel_url=adaptive_repair_url,
        method='POST',
        json_data=payload,
    )

    if return_error:
        module.fail_json(msg=return_error, **result)

    # Get the updated settings and print them for testing purposes
    saas_settings_result, return_error = axonops.do_request(adaptive_repair_url)
    if return_error:
        module.fail_json(msg=return_error, **result)

    result['saas_settings_result'] = saas_settings_result

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
