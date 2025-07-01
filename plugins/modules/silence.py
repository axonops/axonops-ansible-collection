#!/usr/bin/python


DOCUMENTATION = r'''
---
module: axonops.axonops.silence

short_description: Set a Silence.

version_added: "1.0.0"

description: Set a Silence on AxonOps SaaS.

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
            - Set the state of the Silence
            - The default is TRUE
        required: false
        type: bool
    schedule:
        description:
            - Set the schedule for the Silence.
            - leave it to default if is not a recurring Silence.
            - It is used to identify the Silence.
            - The default is  '0 * * * *'.
        required: false
        type: str
    schedule_expr:
        description:
            - Set if the silence is recurring or not.
            - The default is FALSE
        required: true
        type: bool
    duration:
        description:
            - Set the duration of the Silence.
        required: true
        type: str
    dc:
        description:
            - Set datacenter or specific node.
            - The default is []
        required: false
        type: dict
'''

EXAMPLES = r'''
  - name: Set a silence for 1h
      axonops.axonops.silence:
        auth_token: '{{ secret }}'
        org: my_company
        cluster: my_cluster
        duration: 1h


  - name: Set a silence for 3h every 1st of the month
      axonops.axonops.silence:
        auth_token: '{{ secret }}'
        org: my_company
        cluster: my_cluster
        duration: 3h
        active: true
        schedule_expr: '0 * 1 * *'
        schedule: true


'''
import uuid


from ansible.module_utils.basic import AnsibleModule
from ansible_collections.axonops.axonops.plugins.module_utils.axonops import AxonOps
from ansible_collections.axonops.axonops.plugins.module_utils.axonops_utils import make_module_args, \
    dicts_are_different


def run_module():
    module_args = make_module_args({
        'active': {'type': 'bool', 'default': True},
        'schedule': {'type': 'bool', 'default': False},
        'schedule_expr': {'type': 'str', 'default': '0 * * * *'},
        'duration': {'type': 'str','required': True},
        'dc': {'type': 'list', 'default': []},
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

    silence_window_url = (f"/api/v1/silenceWindow/"
                          f"{module.params['org']}/{axonops.get_cluster_type()}/{module.params['cluster']}")

    saas_settings, return_error = axonops.do_request(silence_window_url)
    if return_error:
        module.fail_json(msg=return_error, **result)

    existing_silence = None
    # use CronExpr to recognise if it is a new silence or not
    if saas_settings:
        for silence in saas_settings:
            if silence['CronExpr'] == module.params['schedule_expr']:
                existing_silence = silence

    if existing_silence:
        current_setting = {
            'active': existing_silence['Active'],
            'schedule_expr': existing_silence['CronExpr'],
            'schedule': existing_silence['IsRecurring'],
            'duration': existing_silence['Duration'],
            'dc': existing_silence['DCs'] if 'DCs' in existing_silence else [],
        }
    else:
        current_setting = {
            'Active': False,
            'schedule_expr': '0 * * * *',
            'schedule': False,
            'duration': '',
            'dc': [],
        }

    requested_setting = {
        'active': module.params['active'],
        'schedule_expr': module.params['schedule_expr'],
        'schedule': module.params['schedule'],
        'duration': module.params['duration'],
        'dc': module.params['dc'],
    }

    payload = {
        'ID': existing_silence['ID'] if existing_silence else str(uuid.uuid4()),
        'Active': requested_setting['active'],
        'CronExpr': requested_setting['schedule_expr'],
        'IsRecurring': requested_setting['schedule'],
        'Duration': requested_setting['duration'],
        'DCs': requested_setting['dc'],
    }

    changed = dicts_are_different(current_setting, requested_setting)
    result['diff'] = {'before': current_setting, 'after': requested_setting}
    result['changed'] = changed

    if module.check_mode or not changed:
        module.exit_json(**result)
        return

    if changed and existing_silence:
        _, return_error = axonops.do_request(
            rel_url=f'{silence_window_url}/{existing_silence["ID"]}',
            method='DELETE',
            json_data=[existing_silence['ID']],
        )

        if return_error:
            module.fail_json(msg=return_error, **result)

    if requested_setting['active']:
        _, return_error = axonops.do_request(
            rel_url=silence_window_url,
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
