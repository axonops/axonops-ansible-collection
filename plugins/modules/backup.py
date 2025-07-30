#!/usr/bin/python


DOCUMENTATION = r'''
---
module: axonops_backup

short_description: Set the Backup.

version_added: "1.0.0"

description: Set the backup(s) for your cluster on AxonOps SaaS.

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
            - Cluster where to apply the Backup.
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
'''

EXAMPLES = r'''
# setup backup to Azure blob on cluster `my_cluster` of `my_company`
  - name: Setup backup to azure blob using MSI for auth
    axonops.axonops.backup:
        org: my_company
        cluster: my_cluster
        present: true
        local_retention: 10d
        remote_path: /mybackup/path
        remote_retention: 60d
        remote_type: azure
        tag: "{{ item.tag }}"
        datacenters: dc1
        schedule: True
        schedule_expr: '0 1 * * *'
        azure_account: blob_account_name
        azure_use_msi: true

# setup backup to S3 bucket on cluster `my_cluster` of `my_company`
  - name: Setup backup to azure blob using MSI for auth
    axonops.axonops.backup:
        org: my_company
        cluster: my_cluster
        present: true
        local_retention: 10d
        remote_path: /mybackup/path
        remote_retention: 60d
        remote_type: s3
        tag: "{{ item.tag }}"
        datacenters: dc1
        schedule: True
        schedule_expr: '0 1 * * *'
        s3_region: eu-west-1
        s3_access_key_id: key-id
        s3_secret_access_key: access-key
        s3_acl: private
'''

RETURN = r'''
url:
    description: The endpoint url.
    type: str
    returned: always

'''

import json
import uuid

from ansible.module_utils.basic import AnsibleModule
from ansible_collections.axonops.axonops.plugins.module_utils.axonops import AxonOps
from ansible_collections.axonops.axonops.plugins.module_utils.axonops_utils import make_module_args, \
    dicts_are_different, string_to_bool, string_or_none, bool_to_string


def run_module():
    module_args = make_module_args({
        'present': {'type': 'bool', 'default': True},
        'local_retention': {'type': 'str', 'default': "10d"},
        'remote_path': {'type': 'str', 'required': False, 'default': ''},
        'remote_retention': {'type': 'str', 'default': "60d"},
        'remote_type': {'type': 'str', 'required': False, 'default': 'local', 'choices': ['local', 's3', 'sftp', 'azure']},
        'timeout': {'type': 'str', 'default': "10h"},
        'transfers': {'type': 'int', 'default': 1},
        'remote': {'type': 'bool', 'default': False},
        'tps_limit': {'type': 'int', 'default': 50},
        'bw_limit': {'type': 'str', 'required': False, 'default': ''},
        # 'dynamic_remote_fields': {'type':'list', 'default': []},
        'tag': {'type': 'str', 'required': True},
        'datacenters': {'type': 'list', 'required': True},
        'nodes': {'type': 'list', 'default': []},
        'tables_keyspace': {'type': 'list'},
        'tables': {'type': 'list'},
        'keyspaces': {'type': 'list', 'default': []},
        'schedule': {'type': 'bool', 'default': True},
        'schedule_expr': {'type': 'str', 'default': '0 1 * * *'},
        # AWS S3 remote only
        's3_region': {'type': 'str'},
        's3_access_key_id': {'type': 'str'},
        's3_secret_access_key': {'type': 'str'},
        's3_storage_class': {'required': False, 'default': 'STANDARD',
                             'choices': ['default', 'STANDARD', 'reduced_redundancy',
                                         'standard_ia', 'onezone_ia', 'glacier', 'deep_archive',
                                         'intelligent_tiering']},
        's3_acl': {'required': False, 'default': 'private', 'choices': ['private', 'public-read', 'public-read-write',
                                                                        'authenticated-read', 'bucket-owner-read']},
        's3_encryption': {'required': False, 'default': 'AES256', 'choices': ['none', 'AES256']},
        's3_no_check_bucket': {'type': 'bool', 'default': False},
        's3_disable_checksum': {'type': 'bool', 'default': False},
        # SSH/SFTP remote only
        'host': {'type': 'str'},
        'ssh_user': {'type': 'str', 'required': False, 'default': ''},
        'ssh_pass': {'type': 'str', 'required': False, 'default': ''},
        'key_file': {'type': 'str', 'required': False, 'default': ''},
        # Azure Blob only
        'azure_account': {'type': 'str'},
        'azure_endpoint': {'type': 'str', 'required': False},
        'azure_key': {'type': 'str', 'required': False},
        'azure_use_msi': {'type': 'bool', 'default': False},
        'azure_msi_object_id': {'type': 'str', 'required': False},
        'azure_msi_client_id': {'type': 'str', 'required': False},
        'azure_msi_mi_res_id': {'type': 'str', 'required': False},
    })

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
        required_if=[
            ('remote', True, ('remote_path', 'remote_type',)),
            ('remote_type', 's3', ('s3_region',)),
            ('remote_type', 'azure', ('azure_account',))
        ],
        mutually_exclusive=[
            ('tables', 'keyspaces'),
            ('tables_keyspace', 'keyspaces'),
            ('azure_msi_object_id', 'azure_msi_client_id', 'azure_msi_mi_res_id')
        ],
        required_together=[
            ('tables', 'tables_keyspace'),
        ],
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

    schedule_snapshot_url = (f"/api/v1/cassandraScheduleSnapshot/"
                             f"{module.params['org']}/{axonops.get_cluster_type()}/{module.params['cluster']}")

    saas_backups, return_error = axonops.do_request(schedule_snapshot_url)
    if return_error:
        module.fail_json(msg=return_error, **result)

    backup_details = None
    existing_backup = None
    existing_backup_details = None

    # check if the backup already exists based on the tag attribute
    if saas_backups['ScheduledSnapshots']:
        for backup in saas_backups['ScheduledSnapshots']:
            for param in backup['Params']:
                if "BackupDetails" in param:
                    backup_details = json.loads(param['BackupDetails'])
                    if 'tag' in backup_details:
                        if backup_details['tag'] == module.params['tag']:
                            existing_backup = backup
                            existing_backup_details = backup_details

    # if backup was found
    if existing_backup_details and backup_details:
        if existing_backup_details['RemoteConfig'] != '':
            remote_config = {}
            remote_config_string_dict = existing_backup_details['RemoteConfig'].split('\n')
            for remote_config_string in remote_config_string_dict:
                parts = remote_config_string.split('=', 1)
                if len(parts) > 1:
                    remote_config[parts[0].strip()] = parts[1].strip()

            # for remote backups s3
            if existing_backup_details['remoteType'] == 's3':
                current_setting = {
                    'present': True,
                    'ID': existing_backup['ID'],
                    'local_retention': existing_backup_details['LocalRetentionDuration'],
                    'remote_path': existing_backup_details['remotePath'],
                    'remote_retention': existing_backup_details['RemoteRetentionDuration'],
                    'remote_type': existing_backup_details['remoteType'],
                    'timeout': existing_backup_details['timeout'],
                    'transfers': existing_backup_details['transfers'],
                    'remote': True,
                    'tps_limit': existing_backup_details['tpslimit'],
                    'bw_limit': existing_backup_details['bwlimit'],
                    'tag': existing_backup_details['tag'],
                    'datacenters': existing_backup_details['datacenters'],
                    'nodes': existing_backup_details['nodes'] if 'nodes' in existing_backup_details else [],
                    'tables': existing_backup_details['tables'] if 'tables' in existing_backup_details else [],
                    'keyspaces': existing_backup_details['keyspaces'] if 'keyspaces' in existing_backup_details else [],
                    'schedule': existing_backup_details['schedule'],
                    'schedule_expr': existing_backup_details['scheduleExpr'],
                    's3_region': string_or_none(remote_config.get('region')),
                    's3_access_key_id': string_or_none(remote_config.get('access_key_id')),
                    's3_secret_access_key': string_or_none(remote_config.get('secret_access_key')),
                    's3_storage_class': string_or_none(remote_config.get('storage_class')),
                    's3_acl': string_or_none(remote_config.get('acl')),
                    's3_encryption': string_or_none(remote_config.get('server_side_encryption')),
                    's3_no_check_bucket': string_to_bool(remote_config.get('no_check_bucket')),
                    's3_disable_checksum': string_to_bool(remote_config.get('disable_checksum')),
                }
            elif existing_backup_details['remoteType'] == 'sftp':
                current_setting = {
                    'present': True,
                    'ID': existing_backup['ID'],
                    'local_retention': existing_backup_details['LocalRetentionDuration'],
                    'remote_path': existing_backup_details['remotePath'],
                    'remote_retention': existing_backup_details['RemoteRetentionDuration'],
                    'remote_type': existing_backup_details['remoteType'],
                    'timeout': existing_backup_details['timeout'],
                    'transfers': existing_backup_details['transfers'],
                    'remote': True,
                    'tps_limit': existing_backup_details['tpslimit'],
                    'bw_limit': existing_backup_details['bwlimit'],
                    'tag': existing_backup_details['tag'],
                    'datacenters': existing_backup_details['datacenters'],
                    'nodes': existing_backup_details['nodes'] if 'nodes' in existing_backup_details else [],
                    'tables': existing_backup_details['tables'] if 'tables' in existing_backup_details else [],
                    'keyspaces': existing_backup_details['keyspaces'] if 'keyspaces' in existing_backup_details else [],
                    'schedule': existing_backup_details['schedule'],
                    'schedule_expr': existing_backup_details['scheduleExpr'],
                    'host': remote_config['host'] if 'host' in remote_config else '',
                    'ssh_user': remote_config['user'] if 'user' in remote_config else '',
                    'ssh_pass': remote_config['pass'] if 'pass' in remote_config else '',
                    'key_file': remote_config['key_file'] if 'key_file' in remote_config else ''
                }
            elif existing_backup_details['remoteType'] == 'azure':
                current_setting = {
                    'present': True,
                    'ID': existing_backup['ID'],
                    'local_retention': existing_backup_details['LocalRetentionDuration'],
                    'remote_path': existing_backup_details['remotePath'],
                    'remote_retention': existing_backup_details['RemoteRetentionDuration'],
                    'remote_type': existing_backup_details['remoteType'],
                    'timeout': existing_backup_details['timeout'],
                    'transfers': existing_backup_details['transfers'],
                    'remote': True,
                    'tps_limit': existing_backup_details['tpslimit'],
                    'bw_limit': existing_backup_details['bwlimit'],
                    'tag': existing_backup_details['tag'],
                    'datacenters': existing_backup_details['datacenters'],
                    'nodes': existing_backup_details['nodes'] if 'nodes' in existing_backup_details else [],
                    'tables': existing_backup_details['tables'] if 'tables' in existing_backup_details else [],
                    'keyspaces': existing_backup_details['keyspaces'] if 'keyspaces' in existing_backup_details else [],
                    'schedule': existing_backup_details['schedule'],
                    'schedule_expr': existing_backup_details['scheduleExpr'],
                    'azure_account': string_or_none(remote_config.get('account')),
                    'azure_endpoint': string_or_none(remote_config.get('endpoint')),
                    'azure_key': string_or_none(remote_config.get('key')),
                    'azure_use_msi': string_or_none(remote_config.get('use_msi')),
                    'azure_msi_object_id': string_or_none(remote_config.get('msi_object_id')),
                    'azure_msi_client_id': string_or_none(remote_config.get('msi_client_id')),
                    'azure_msi_mi_res_id': string_or_none(remote_config.get('msi_mi_res_id')),
                }
        else:
            # for local only backups
            current_setting = {
                'present': True,
                'ID': existing_backup['ID'],
                'local_retention': existing_backup_details['LocalRetentionDuration'],
                'remote': False,
                'tag': existing_backup_details['tag'],
                'datacenters': existing_backup_details['datacenters'],
                'nodes': existing_backup_details['nodes'] if 'nodes' in existing_backup_details else [],
                'tables': existing_backup_details['tables'] if 'tables' in existing_backup_details else [],
                'keyspaces': existing_backup_details['keyspaces'] if 'keyspaces' in existing_backup_details else [],
                'schedule': existing_backup_details['schedule'],
                'schedule_expr': existing_backup_details['scheduleExpr'],
            }
    else:
        # if new backup
        current_setting = {
            'present': False,
        }

    # check if user has specified a keyspace
    if module.params['keyspaces']:
        requested_keyspaces = module.params['keyspaces']
    elif module.params['tables_keyspace']:
        requested_keyspaces = module.params['tables_keyspace']
    else:
        requested_keyspaces = []

    # check if user has specified a table
    requested_tables = []
    for table in module.params['tables'] or []:
        split = table.split('.')
        requested_tables.append({'Name': split[1]})

    requested_nodes, return_error = axonops.find_nodes_ids(module.params['nodes'], module.params['org'],
                                                           module.params['cluster'])
    if return_error:
        module.fail_json(msg=return_error, **result)

    # if remote backup
    if module.params['remote']:
        # if AWS S3
        if module.params['remote_type'] == 's3':
            requested_setting = {
                'present': module.params['present'],
                'ID': existing_backup['ID'] if existing_backup else str(uuid.uuid4()),
                'local_retention': module.params['local_retention'],
                'remote_path': module.params['remote_path'],
                'remote_retention': module.params['remote_retention'],
                'remote_type': module.params['remote_type'].lower(),
                'timeout': module.params['timeout'],
                'transfers': module.params['transfers'],
                'remote': module.params['remote'],
                'tps_limit': module.params['tps_limit'],
                'bw_limit': module.params['bw_limit'],
                'tag': module.params['tag'],
                'datacenters': module.params['datacenters'],
                'nodes': requested_nodes,
                'tables': requested_tables,
                'keyspaces': requested_keyspaces,
                'schedule': module.params['schedule'],
                'schedule_expr': module.params['schedule_expr'],
                's3_region': module.params['s3_region'],
                's3_access_key_id': module.params['s3_access_key_id'],
                's3_secret_access_key': module.params['s3_secret_access_key'],
                's3_storage_class': module.params['s3_storage_class'],
                's3_acl': module.params['s3_acl'],
                's3_encryption': module.params['s3_encryption'],
                's3_no_check_bucket': module.params['s3_no_check_bucket'],
                's3_disable_checksum': module.params['s3_disable_checksum'],
            }
        elif module.params['remote_type'] == 'sftp':
            requested_setting = {
                'present': module.params['present'],
                'ID': existing_backup['ID'] if existing_backup else str(uuid.uuid4()),
                'local_retention': module.params['local_retention'],
                'remote_path': module.params['remote_path'],
                'remote_retention': module.params['remote_retention'],
                'remote_type': module.params['remote_type'].lower(),
                'timeout': module.params['timeout'],
                'transfers': module.params['transfers'],
                'remote': module.params['remote'],
                'tps_limit': module.params['tps_limit'],
                'bw_limit': module.params['bw_limit'],
                'tag': module.params['tag'],
                'datacenters': module.params['datacenters'],
                'nodes': requested_nodes,
                'tables': requested_tables,
                'keyspaces': requested_keyspaces,
                'schedule': module.params['schedule'],
                'schedule_expr': module.params['schedule_expr'],
                'host': module.params['host'],
                'ssh_user': module.params['ssh_user'],
                'ssh_pass': module.params['ssh_pass'],
                'key_file': module.params['key_file'],
            }
        elif module.params['remote_type'] == 'azure':
            requested_setting = {
                'present': module.params['present'],
                'ID': existing_backup['ID'] if existing_backup else str(uuid.uuid4()),
                'local_retention': module.params['local_retention'],
                'remote_path': module.params['remote_path'],
                'remote_retention': module.params['remote_retention'],
                'remote_type': module.params['remote_type'].lower(),
                'timeout': module.params['timeout'],
                'transfers': module.params['transfers'],
                'remote': module.params['remote'],
                'tps_limit': module.params['tps_limit'],
                'bw_limit': module.params['bw_limit'],
                'tag': module.params['tag'],
                'datacenters': module.params['datacenters'],
                'nodes': requested_nodes,
                'tables': requested_tables,
                'keyspaces': requested_keyspaces,
                'schedule': module.params['schedule'],
                'schedule_expr': module.params['schedule_expr'],
                'azure_account': module.params['azure_account'],
                'azure_endpoint': module.params['azure_endpoint'],
                'azure_key': module.params['azure_key'],
                'azure_use_msi': module.params['azure_use_msi'],
                'azure_msi_object_id': module.params['azure_msi_object_id'],
                'azure_msi_client_id': module.params['azure_msi_client_id'],
                'azure_msi_mi_res_id': module.params['azure_msi_mi_res_id'],
            }
    else:
        # for local only
        requested_setting = {
            'present': module.params['present'],
            'ID': existing_backup['ID'] if existing_backup else str(uuid.uuid4()),
            'local_retention': module.params['local_retention'],
            'remote': module.params['remote'],
            'tag': module.params['tag'],
            'datacenters': module.params['datacenters'],
            'nodes': requested_nodes,
            'tables': requested_tables,
            'keyspaces': requested_keyspaces,
            'schedule': module.params['schedule'],
            'schedule_expr': module.params['schedule_expr'],
        }

    # if the backup is remote, create the remote_config accordingly
    if requested_setting['remote']:
        if requested_setting['remote_type'] == 's3':
            remote_config_dict = {
                'type': requested_setting['remote_type'],
                'provider': 'AWS',
                'region': requested_setting['s3_region'],
                'acl': requested_setting['s3_acl'],
                'server_side_encryption': requested_setting['s3_encryption'],
                'storage_class': requested_setting['s3_storage_class'],
                'no_check_bucket': bool_to_string(requested_setting['s3_no_check_bucket']),
                'disable_checksum': bool_to_string(requested_setting['s3_disable_checksum']),
            }

            if requested_setting['s3_secret_access_key'] and requested_setting['s3_access_key_id']:
                remote_config_dict['env_auth'] = 'false'
                remote_config_dict['access_key_id'] = requested_setting['s3_access_key_id']
                remote_config_dict['secret_access_key'] = requested_setting['s3_secret_access_key']
            else:
                remote_config_dict['env_auth'] = 'true'

            # transform the dict in the prom like format needed by AxonOps
            remote_config = "\n".join([f"{k} = {v}" for k, v in remote_config_dict.items()])
        elif requested_setting['remote_type'] == 'sftp':
            remote_config_dict = {
                'type': requested_setting['remote_type'],
                'host': requested_setting['host'],
                'user': requested_setting['ssh_user'],
                'pass': requested_setting['ssh_pass'] if 'ssh_pass' in requested_setting else '',
                'port': requested_setting['port'] if 'port' in requested_setting else '',
                'key_file': requested_setting['key_file'] if 'key_file' in requested_setting else '',
            }

            remote_config = "\n".join([f"{k} = {v}" for k, v in remote_config_dict.items()])
        elif requested_setting['remote_type'] == 'azure':
            # Note if use_msi is true then need to unset env_auth
            remote_config_dict = {
                'type': 'azureblob',
                'account': requested_setting['azure_account'],
            }

            if requested_setting.get('azure_use_msi'):
                remote_config_dict['use_msi'] = 'true'
                if requested_setting['azure_msi_object_id']:
                    remote_config_dict['msi_object_id '] = requested_setting['azure_msi_object_id']
                if requested_setting['azure_msi_client_id']:
                    remote_config_dict['msi_client_id '] = requested_setting['azure_msi_client_id']
                if requested_setting['azure_msi_mi_res_id']:
                    remote_config_dict['msi_mi_res_id '] = requested_setting['azure_msi_mi_res_id']

            # transform the dict in the prom like format needed by AxonOps
            remote_config = "\n".join([f"{k} = {v}" for k, v in remote_config_dict.items()])

        else:
            remote_config = ''
            module.fail_json(msg=f"remote type {requested_setting['remote_type']} unsupported", **result)

        payload = {
            'ID': requested_setting['ID'],
            'LocalRetentionDuration': requested_setting['local_retention'],
            'remoteConfig': remote_config,
            'remotePath': requested_setting['remote_path'],
            'RemoteRetentionDuration': requested_setting['remote_retention'],
            'remoteType': requested_setting['remote_type'],
            'timeout': requested_setting['timeout'],
            'transfers': requested_setting['transfers'],
            'Remote': requested_setting['remote'],
            'tpslimit': requested_setting['tps_limit'],
            'bwlimit': requested_setting['bw_limit'],
            'tag': requested_setting['tag'],
            'datacenters': requested_setting['datacenters'],
            'nodes': requested_setting['nodes'],
            'tables': requested_setting['tables'],
            'allTables': len(requested_setting['tables']) == 0,
            'allNodes': len(requested_setting['nodes']) == 0,
            'keyspaces': requested_setting['keyspaces'],
            'schedule': requested_setting['schedule'],
            'scheduleExpr': requested_setting['schedule_expr'],
        }
    else:
        payload = {  # only for local backups
            'ID': requested_setting['ID'],
            'LocalRetentionDuration': requested_setting['local_retention'],
            'Remote': False,
            'tag': requested_setting['tag'],
            'datacenters': requested_setting['datacenters'],
            'nodes': requested_setting['nodes'],
            'tables': requested_setting['tables'],
            'keyspaces': requested_setting['keyspaces'],
            'schedule': requested_setting['schedule'],
            'scheduleExpr': requested_setting['schedule_expr'],
        }

    # print differences if it is needed
    changed = dicts_are_different(current_setting, requested_setting)
    result['diff'] = {'before': current_setting, 'after': requested_setting}
    result['changed'] = changed

    # if it is in check mode, or it is not changed, exit
    if module.check_mode or not changed:
        module.exit_json(**result)
        return

    if changed and existing_backup:
        _, return_error = axonops.do_request(
            rel_url=schedule_snapshot_url,
            method='DELETE',
            json_data=[existing_backup['ID']],
        )

        if return_error:
            module.fail_json(msg=return_error, **result)

    cassandra_snapshot_url = \
        f"/api/v1/cassandraSnapshot/{module.params['org']}/{axonops.get_cluster_type()}/{module.params['cluster']}"
    if requested_setting['present']:
        _, return_error = axonops.do_request(
            rel_url=cassandra_snapshot_url,
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
