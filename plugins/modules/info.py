#!/usr/bin/python


DOCUMENTATION = r'''
---
module: info

short_description: Retrieve data regarding the clusters.

version_added: "0.6.3"

description: Retrieve data regarding the clusters from the AxonOps API.

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
            - The name of the cluster to retrieve data for.
            - It can be read from the environment variable AXONOPS_CLUSTER.
        required: false
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
            - The type of the cluster (e.g. cassandra, kafka).
            - It can be read from the environment variable AXONOPS_CLUSTER_TYPE.
        required: false
        type: str
        default: cassandra
    use_saml:
        description:
            - Whether to authenticate via SAML.
            - It can be read from the environment variable AXONOPS_USE_SAML.
            - This module is also used as a health/config check; if the request
              fails it is retried once with use_saml flipped to the opposite
              value. If the opposite value succeeds the module fails with a
              message telling you the SAML configuration is wrong.
        required: false
        type: bool
        default: false
'''

EXAMPLES = r'''
# Retrieve data for a cluster on SaaS
  - name: Retrieve cluster data on SaaS
    axonops.axonops.info:
      auth_token: '{{ secret }}'
      org: example
      cluster: my-cluster
    register: info

'''

RETURN = r'''
orgs:
    description: The organisation/cluster tree as returned by the AxonOps API.
    returned: always
    type: dict
    sample:
        children:
            - name: demo
              type: org
              children:
                - name: cassandra
                  type: type
                  children:
                    - name: demo-cluster
                      type: cassandra
                      status: 0
unhealthy:
    description:
        - List of components whose C(status) is not 0.
        - Only returned when the health check fails; its presence means the
          module failed.
    returned: on failure (when one or more components report a non-zero status)
    type: list
    elements: dict
    contains:
        type:
            description: The component type (e.g. cassandra, kafka).
            type: str
            returned: always
        name:
            description: The component name.
            type: str
            returned: always
        status:
            description: The numeric status reported by the API (non-zero).
            type: int
            returned: always
        label:
            description: Human-readable status label (Warning, Error, or Unknown).
            type: str
            returned: always
        message:
            description: 'Formatted "<type>/<name>: <label>" summary string.'
            type: str
            returned: always
    sample:
        - type: cassandra
          name: demo-cluster
          status: 1
          label: Warning
          message: "cassandra/demo-cluster: Warning"
'''

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.axonops.axonops.plugins.module_utils.axonops_utils import make_module_args, get_axonops_instance

ORGS_URL = "/api/v1/orgs"

# Map the numeric status returned by the orgs endpoint to a human label.
# Anything non-zero that is not explicitly mapped is treated as "Unknown".
STATUS_LABELS = {
    1: "Warning",
    2: "Error",
}


def collect_unhealthy(node):
    """
    Recursively walk the orgs tree and return a list of entries whose
    ``status`` is not 0.

    Mirrors the jq expression that selects leaf nodes with ``status != 0`` and
    formats them as ``"<type>/<name>: <label>"``. Recursing on ``children``
    (rather than assuming a fixed depth) keeps it robust to extra nesting.
    """
    unhealthy = []

    if isinstance(node, dict):
        status = node.get('status')
        if status is not None and status != 0:
            label = STATUS_LABELS.get(status, "Unknown")
            unhealthy.append({
                'type': node.get('type'),
                'name': node.get('name'),
                'status': status,
                'label': label,
                'message': "{type}/{name}: {label}".format(
                    type=node.get('type'),
                    name=node.get('name'),
                    label=label,
                ),
            })
        for child in node.get('children', []) or []:
            unhealthy.extend(collect_unhealthy(child))

    return unhealthy


def check_orgs(params):
    """
    Build an AxonOps instance from ``params`` and query the orgs endpoint.

    Returns a tuple ``(orgs_output, error)`` where ``error`` is non-empty if
    either the instance failed to initialise (e.g. login) or the request
    failed. ``use_saml`` is consumed when the instance is constructed (it
    determines the base URL), so flipping it requires a fresh call here.
    """
    axonops = get_axonops_instance(params)

    if axonops.errors:
        return None, ' '.join(axonops.errors)

    orgs_output, return_error = axonops.do_request(ORGS_URL)
    if return_error:
        return None, return_error

    return orgs_output, None


def run_module():
    module_args = make_module_args({
    })

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
    )

    result = {
        'changed': False,
    }

    requested_saml = module.params.get('use_saml', False)

    # First attempt with the SAML setting as configured by the user.
    orgs_output, return_error = check_orgs(module.params)

    if return_error:
        # The request failed. Treat this as a health/config check: retry once
        # with use_saml flipped to the opposite of what the user configured.
        retry_params = dict(module.params)
        retry_params['use_saml'] = not requested_saml

        retry_output, retry_error = check_orgs(retry_params)

        if not retry_error:
            # The opposite SAML setting works, so the user misconfigured it.
            module.fail_json(
                msg=(
                    "Connection failed with use_saml={requested} but succeeded "
                    "with use_saml={opposite}. Your SAML configuration is wrong: "
                    "set use_saml (or the AXONOPS_USE_SAML environment variable) "
                    "to {opposite}.".format(
                        requested=requested_saml,
                        opposite=not requested_saml,
                    )
                ),
                original_error=return_error,
                **result
            )

        # Both settings failed: surface the original error.
        module.fail_json(msg=return_error, **result)

    result['orgs'] = orgs_output

    # Health check: fail if any cluster/node reports a non-zero status.
    unhealthy = collect_unhealthy(orgs_output)
    if unhealthy:
        result['unhealthy'] = unhealthy
        module.fail_json(
            msg="Unhealthy components detected: " + "; ".join(
                entry['message'] for entry in unhealthy
            ),
            **result
        )

    module.exit_json(**result)


def main():
    run_module()


if __name__ == '__main__':
    main()
