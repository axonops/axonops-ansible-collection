#!/usr/bin/python3

DOCUMENTATION = r'''
---
module: axonops_log_alert_rule

short_description: Configure a log alerting rule for AxonOps

version_added: '1.0.0'

description: Configure a log alerting rule for AxonOps

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
    present:
        description:
            - Set the state of the log Alert Route.
            - The default is TRUE.
        required: false
        type: bool
    name:
        description:
            - Name of the alert.
            - Used to identify the alert
        required: true
        type: str
    cluster_type:
        description:
            - The typo of cluster, cassandra, DSE, etc.
            - Default is cassandra
            - It can be read from the environment variable AXONOPS_CLUSTER_TYPE.
        required: false
        type: str
    content:
        description:
            - Content to search in the log.
        required: false
        type: str
    description:
        description:
            - Description of the alert.
        required: false
        type: str
    warning_value:
        description:
            - The warning threshold of the alert.
        required: true
        type: int
    critical_value:
        description:
            - The critical threshold of the alert.
        required: true
        type: int
    duration:
        description:
            - The duration of the alert.
            - For how long in the past you want the scrape log.
        required: true
        type: str
    operator
        description:
            - The operator to use un the alert query.
            - The default value is '>='.
        required: false
        choices: ['=', '>=', '>', '<=', '<', '!=']
        type: str
    level:
        description:
            - The log level where the alert operate.
            - If left empty the alert will search in all log levels
            - The default value is empty.
            - Multivalued parameter accepted. Use comma as separator.
        required: false
        choices: ['debug', 'error', 'warning', 'info']
        type: str
    type:
        description:
            - The log type where the alert operate.
            - If left empty the alert will search in all log types.
            - The default value is empty.
            - Multivalued parameter accepted. Use comma as separator.
        required: false
        type: str
    source:
        description:
            - The log source where the alert operate.
            - If left empty the alert will search in all log source.
            - The default value is empty.
            - Multivalued parameter accepted. Use comma as separator.
        required: false
        type: str
'''

EXAMPLES = r'''
# alert if a node went down in the last 30s
  - name: set a alert rule
    axonops.axonops.log_alert_rule:
      auth_token: "{{ secret }}"
      org: my_company
      cluster: single_instance
      name: 'Node Down'
      warning_value: 1
      critical_value: 10
      duration: 30s
      content: 'DOWN'
# alert if a node went down in the last 30s, searching only in the debug and error logs
  - name: set a alert rule
    axonops.axonops.log_alert_rule:
      auth_token: "{{ secret }}"
      org: my_company
      cluster: single_instance
      name: 'Node Down'
      warning_value: 1
      critical_value: 10
      duration: 30s
      content: 'DOWN'
      level: error, debug
'''

import re
import json
import uuid

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.axonops.axonops.plugins.module_utils.axonops import AxonOps
from ansible_collections.axonops.axonops.plugins.module_utils.axonops_utils import make_module_args, find_by_field, dicts_are_different, get_value_by_name, normalize_numbers, get_integration_id_by_name



def run_module():
    module_args = make_module_args({
        'name': {'type': 'str', 'required': True},
        'content': {'type': 'str', 'default': ''},
        'description': {'type': 'str', 'default': ''},
        'warning_value': {'type': 'int'},
        'critical_value': {'type': 'int'},
        'duration': {'type': 'str'},
        'present': {'type': 'bool', 'default': True},
        'operator': {'type': 'str', 'choices': ['=', '>=', '>', '<=', '<', '!='], 'default': '>='},
        'level': {'type': 'str', 'default': ''},
        'type': {'type': 'str', 'default': ''},
        'source': {'type': 'str', 'default': ''},
        'dc': {'type': 'list', 'default': []},
        'rack': {'type': 'list', 'default': []},
        'host_id': {'type': 'list', 'default': []},
        'routing': {'type': 'dict', 'default': {}}
    })

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )
    result = {
        'changed': False,
    }

    # check if level is correct or empty
    level_choices = ['debug', 'error', 'warning', 'info']
    for level in module.params['level'].split(',') or []:
        if level not in level_choices and level:
            module.fail_json(msg=f'{level} is not a valid level, accepted: {level_choices}')
            return

    org = module.params['org']
    cluster = module.params['cluster']

    axonops = AxonOps(module.params['org'], auth_token=module.params['auth_token'], base_url=module.params['base_url'],
                      username=module.params['username'], password=module.params['password'],
                      cluster_type=module.params['cluster_type'], api_token=module.params['api_token'],
                      override_saas=module.params['override_saas'])

    if axonops.errors:
        module.fail_json(msg=' '.join(axonops.errors), **result)

    alerts_url = f"/api/v1/alert-rules/{org}/{axonops.get_cluster_type()}/{cluster}"

    # Get existing alerts
    existing_alerts, error = axonops.do_request(alerts_url)
    if error is not None:
        module.fail_json(msg=error)
        return

    # check if it is an old alert or a new one
    old_alert = None
    if existing_alerts:
        for alert in existing_alerts['metricrules']:
            if 'events' in alert['expr'] and alert['alert'] == module.params['name']:
                old_alert = alert

    # Bail out early if the alert doesn't exist and we don't want it to
    if not old_alert and not module.params['present']:
        module.exit_json(**result)
        return

    # If it is an old alert, read it
    if old_alert:
        pattern_external = r'events\{(.+)\}'
        pattern_split_elements = r'(\w+)="((?:[^"\\]|\\.)*?)"'

        match = re.search(pattern_external, old_alert['expr'])

        old_alert_expr = {}
        if match:
            elements_matches = re.findall(pattern_split_elements, match.group(1))
            elements = {key: value for key, value in elements_matches}

            for key, value in elements.items():
                old_alert_expr[key] = value.replace('|',',')

        else:
            module.fail_json(msg=r'pattern not found for expr ' + old_alert['expr'])

        old_integrations = old_alert.get('integrations', {})
        if old_integrations:
            del old_integrations['Type']
            del old_integrations['OverrideError']
            del old_integrations['OverrideInfo']
            del old_integrations['OverrideWarning']
            for route_item in old_integrations['Routing']:
                del route_item['Params']

        old_data = {
            'name': old_alert['alert'],
            'description': old_alert['annotations']['description'],
            'operator': old_alert['operator'],
            'warning_value': old_alert['warningValue'],
            'critical_value': old_alert['criticalValue'],
            'duration': old_alert['for'],
            'content': old_alert_expr['message'] if 'message' in old_alert_expr else '',
            'level': old_alert_expr['level'] if 'level' in old_alert_expr else '',
            'type': old_alert_expr['type'] if 'type' in old_alert_expr else '',
            'source': old_alert_expr['source'] if 'source' in old_alert_expr else '',
            'present': True,
            'integrations': old_alert['integrations']
        }
    else:
        old_data = {'present': False}

    old_data_normalized = normalize_numbers(old_data)


    # create the new alert
    if module.params['present']:
        new_data = {
            'name': module.params['name'],
            'description': module.params['description'],
            'operator': module.params['operator'],
            'warning_value': module.params['warning_value'],
            'critical_value': module.params['critical_value'],
            'duration': module.params['duration'],
            'content': module.params['content'],
            'level': module.params['level'],
            'type': module.params['type'],
            'source': module.params['source'],
            'present': True,
            'integrations': {}
        }
    else:
        new_data = {
            'name': module.params['name'],
            'present': False,
        }

    # create routing override list
    routing = []  # format [{id: 'id33s', severity: 'error'},...]
    for severity in module.params['routing']:
        if severity not in {"error", "warning", "info"}:
            module.fail_json(msg=f'{severity} is not a valid level, accepted: info, warn, error')
        else:
            for override in module.params['routing'][severity]:
                integration_id, error = axonops.find_integration_id_by_name(cluster, override)
                if integration_id is None:
                    module.fail_json(msg=f"Integration name {override} not configured in AxonOps integrations.")
                if error is not None:
                    module.fail_json(msg=error)
                    return
                routing.append({
                    'ID': integration_id if integration_id else "",
                    'Severity': severity,
                })
    if routing:
        new_data['integrations']['Routing'] = routing
    elif 'integrations' in new_data:
        new_data['integrations']['Routing'] = []

    new_data_normalized = normalize_numbers(new_data)

    changed = dicts_are_different(new_data_normalized, old_data_normalized)
    result['changed'] = changed
    result['diff'] = {'before': old_data, 'after': new_data}

    # Exit if in check mode or no changes
    if module.check_mode or not changed:
        module.exit_json(**result)
        return

    # Delete the alert rule and exit, if present is False
    if not module.params['present']:
        if old_alert:
            _, error = axonops.do_request(rel_url=alerts_url + '/' + old_alert["id"], method='DELETE')
            if error is not None:
                module.fail_json(msg=error)
        module.exit_json(**result)
        return

    # create the event string for expr
    events_string = "events{{{message_str}{level_str}{source_str}{type_str}}}".format(
        message_str=",message=\"{}\"".format(module.params['content']) if module.params['content'] else '',
        level_str=",level=\"{}\"".format(module.params['level'].replace(',', '|')) if module.params['level'] else '',
        source_str=",source=\"{}\"".format(
            module.params['source'].replace(',', '|')) if module.params['source'] else '',
        type_str=",type=\"{}\"".format(module.params['type'].replace(',', '|')) if module.params['type'] else ''
    ).replace('{,', '{')

    # Create or update the alert rule
    payload = {
        'alert': module.params['name'],
        'for': module.params['duration'],
        'operator': module.params['operator'],
        'warningValue': module.params['warning_value'],
        'criticalValue': module.params['critical_value'],
        'annotations': {
            'description': module.params['description'],
            'summary': "%s is %s than %s (current value: {{$value}}" % (
                module.params['name'], module.params['operator'], module.params['warning_value']),
        },
        'integrations': new_data['integrations'],
        'expr': events_string,
        'id': old_alert["id"] if old_alert else str(uuid.uuid4()),
    }
    result['payload'] = payload
    _, error = axonops.do_request(rel_url=alerts_url, method='POST', json_data=payload)
    if error is not None:
        result['error'] = error
        module.fail_json(msg=result)
        return

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
