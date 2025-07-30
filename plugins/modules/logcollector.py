#!/usr/bin/python


DOCUMENTATION = r'''
---
module: axonops.axonops.logcollector

short_description: Set the logcollector.

version_added: "1.0.0"

description: Set the logcollector for your cluster on AxonOps SaaS.

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
    name:
        description:
            - Set the name to identify the collector in the AxonOps dash.
        required: true
        type: str


'''

EXAMPLES = r'''
# Set logcollector for the GC on cluster `my_cluster` of `my_company`
  - name: Set logcollector on my_cluster for the GC
    axonops.axonops.logcollector:
      auth_token: "{{ secret }}"
      org: my_company
      cluster: my_cluster
      name: GC grace log file
      interval: 5s
      timeout: 1m
      filename: /var/log/cassandra/gc.log.0.current
      dateFormat: yyyy-MM-ddTHH:mm:ssZ
      readonly: true
'''
import uuid
from copy import copy

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.axonops.axonops.plugins.module_utils.axonops import AxonOps
from ansible_collections.axonops.axonops.plugins.module_utils.axonops_utils import make_module_args, \
    dicts_are_different


def run_module():
    module_args = make_module_args({
        'present': {'type': 'bool', 'required': False, 'default': True},
        'name': {'type': 'str', 'required': True},
        'interval': {'type': 'str', 'required': False, 'default': '5s'},
        'timeout': {'type': 'str', 'required': False, 'default': '1m'},
        'filename': {'type': 'str', 'required': True},
        'dateFormat': {'type': 'str', 'required': False, 'default': 'yyyy-MM-dd HH:mm:ss,SSS'},
        'infoRegex': {'type': 'str', 'required': False, 'default': ''},
        'warningRegex': {'type': 'str', 'required': False, 'default': ''},
        'errorRegex': {'type': 'str', 'required': False, 'default': ''},
        'debugRegex': {'type': 'str', 'required': False, 'default': ''},
        'readonly': {'type': 'bool', 'required': False, 'default': False}
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

    logcollectors_url = \
        f"/api/v1/logcollectors/{module.params['org']}/{axonops.get_cluster_type()}/{module.params['cluster']}"

    logcollectors_api_output, return_error = axonops.do_request(logcollectors_url)
    if return_error:
        module.fail_json(msg=return_error, **result)

    # all the logcollectors
    logcollectors = []

    # the logcollector that we are working on, default empty
    current_logcollector = {}

    for logcollector_api_output in logcollectors_api_output:
        # the file is used to identify the collector
        if logcollector_api_output['filename'] == module.params['filename']:

            current_logcollector = {
                'uuid': logcollector_api_output['uuid'],
                'present': True,
                'name': logcollector_api_output['name'],
                'interval': logcollector_api_output['interval'],
                'timeout': logcollector_api_output['timeout'],
                'filename': logcollector_api_output['filename'],
                'dateFormat': logcollector_api_output['dateFormat'],
                'infoRegex': logcollector_api_output['infoRegex'],
                'warningRegex': logcollector_api_output['warningRegex'],
                'errorRegex': logcollector_api_output['errorRegex'],
                'debugRegex': logcollector_api_output['debugRegex'],
                'readonly': logcollector_api_output['readonly'],
            }

        else:
            logcollectors.append(logcollector_api_output)

    # create the basic requested logcollector for the diff
    requested_logcollector = {
        'uuid': current_logcollector['uuid'] if current_logcollector else str(uuid.uuid4()),
        'present': module.params['present'],
        'name': module.params['name'],
        'interval': module.params['interval'],
        'timeout': module.params['timeout'],
        'filename': module.params['filename'],
        'dateFormat': module.params['dateFormat'],
        'infoRegex': module.params['infoRegex'],
        'warningRegex': module.params['warningRegex'],
        'errorRegex': module.params['errorRegex'],
        'debugRegex': module.params['debugRegex'],
        'readonly': module.params['readonly'],
    }

    changed = dicts_are_different(current_logcollector, requested_logcollector)
    result['diff'] = {'before': current_logcollector, 'after': copy(requested_logcollector)}
    result['changed'] = changed

    # add the mandatory fields to the requested logcollector
    requested_logcollector['id'] = ''
    requested_logcollector['integrations'] = {
        "OverrideError": False,
        "OverrideInfo": False,
        "OverrideWarning": False,
        "Routing": None,
        "Type": ""
    }

    # if it set as present, add it
    if requested_logcollector['present']:
        del requested_logcollector['present']
        logcollectors.append(requested_logcollector)

    if module.check_mode or not changed:
        module.exit_json(**result)
        return

    _, return_error = axonops.do_request(
        rel_url=logcollectors_url,
        method='PUT',
        json_data=logcollectors,
        form_field="addlogs"
    )

    if return_error:
        module.fail_json(msg=return_error, **result)

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
