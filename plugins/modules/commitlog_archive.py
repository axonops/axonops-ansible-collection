#!/usr/bin/python


DOCUMENTATION = r'''
---
module: commitlog_archive

short_description: Set the commitlog archive settings.

version_added: "1.0.0"

description: Set the commitlog archive settings for your cluster on AxonOps SaaS.

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
            - The type of cluster, cassandra, DSE, etc.
            - Default is cassandra
            - It can be read from the environment variable AXONOPS_CLUSTER_TYPE.
        required: false
        type: str

'''

EXAMPLES = r'''

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
        'remote_path': {'type': 'str', 'required': False, 'default': ''},
        'remote_retention': {'type': 'str', 'default': "60d"},
        'remote_type': {'type': 'str', 'required': False, 'default': 'local', 'choices': ['local', 's3', 'sftp']},
        'timeout': {'type': 'str', 'default': "10h"},
        'transfers': {'type': 'int', 'default': 0},
        'bw_limit': {'type': 'str', 'required': False, 'default': ''},
        'datacenters': {'type': 'list', 'required': True},
        # AWS S3 remote only
        's3_region': {'type': 'str', 'default': 'us-east-1'},
        's3_access_key_id': {'type': 'str', 'default': None},
        's3_secret_access_key': {'type': 'str', 'default': None},
        's3_storage_class': {'required': False, 'default': 'STANDARD',
                             'choices': ['default', 'STANDARD', 'reduced_redundancy',
                                         'standard_ia', 'onezone_ia', 'glacier', 'deep_archive',
                                         'intelligent_tiering']},
        's3_acl': {'required': False, 'default': 'private', 'choices': ['private', 'public-read', 'public-read-write',
                                                                        'authenticated-read', 'bucket-owner-read']},
        's3_encryption': {'required': False, 'default': 'AES256', 'choices': ['none', 'AES256']},
        's3_disable_checksum': {'type': 'bool', 'default': False},
        # SSH/SFTP remote only
        'host': {'type': 'str', 'default': None},
        'ssh_user': {'type': 'str', 'default': None},
        'ssh_pass': {'type': 'str', 'default': None},
        'key_file': {'type': 'str', 'default': None}
    })

    module = AnsibleModule(
        argument_spec=module_args,
        supports_check_mode=True,
        required_if=[
            ('remote_type', 's3', ('s3_region',))
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

    commitlog_settings_url = (f"/api/v1/cassandraCommitLogsSettings/"
                              f"{module.params['org']}/{axonops.get_cluster_type()}/{module.params['cluster']}")

    commitlog_settings_actual_list, return_error = axonops.do_request(commitlog_settings_url)
    if return_error:
        module.fail_json(msg=return_error, **result)

    found_settings = {}
    current_setting = {}

    for commitlog_settings_actual in commitlog_settings_actual_list or []:
        if commitlog_settings_actual['remoteType'] == module.params['remote_type']:
            found_settings = commitlog_settings_actual

    if found_settings:
        remote_config = {}
        remote_config_string_dict = found_settings['RemoteConfig'].split('\n')
        for remote_config_string in remote_config_string_dict:
            parts = remote_config_string.split('=', 1)
            if len(parts) > 1:
                remote_config[parts[0].strip()] = parts[1].strip()

        current_setting = {
            'present': True,
            'remote_type': found_settings['remoteType'],
            'timeout': found_settings['timeout'],
            'bw_limit': found_settings['bwlimit'],
            'remote_retention': found_settings['RemoteRetentionDuration'],
            'remote_path': found_settings['remotePath'],
            'datacenters': found_settings['datacenters'],
            'transfers': found_settings['transfers']
        }
        if found_settings['remoteType'] == 's3':
            current_setting['s3_region'] = string_or_none(remote_config.get('region'))
            current_setting['s3_access_key_id'] = string_or_none(remote_config.get('access_key_id'))
            current_setting['s3_storage_class'] = string_or_none(remote_config.get('storage_class'))
            current_setting['s3_acl'] = string_or_none(remote_config.get('acl'))
            current_setting['s3_encryption'] = string_or_none(remote_config.get('server_side_encryption'))
            current_setting['s3_disable_checksum'] = string_to_bool(remote_config.get('disable_checksum'))
        elif found_settings['remoteType'] == 'sftp':
            current_setting['host'] = string_or_none(remote_config.get('host'))
            current_setting['ssh_user'] = string_or_none(remote_config.get('ssh_user'))
            current_setting['key_file'] = string_or_none(remote_config.get('key_file'))

    else:
        current_setting = {
            'present': False
        }

    requested_setting = {
        'present': module.params['present'],
        'remote_type': module.params['remote_type'],
        'timeout': module.params['timeout'],
        'bw_limit': module.params['bw_limit'],
        'remote_retention': module.params['remote_retention'],
        'remote_path': module.params['remote_path'],
        'datacenters': module.params['datacenters'],
        'transfers': module.params['transfers'],
    }

    if module.params['remote_type'] == 's3':
        requested_setting['s3_region'] = module.params['s3_region']
        requested_setting['s3_access_key_id'] = module.params['s3_access_key_id']
        requested_setting['s3_secret_access_key'] = module.params['s3_secret_access_key']
        requested_setting['s3_storage_class'] = module.params['s3_storage_class']
        requested_setting['s3_acl'] = module.params['s3_acl']
        requested_setting['s3_encryption'] = module.params['s3_encryption']
        requested_setting['s3_disable_checksum'] = module.params['s3_disable_checksum']
    elif module.params['remote_type'] == 'sftp':
        requested_setting['host'] = module.params['host']
        requested_setting['ssh_user'] = module.params['ssh_user']
        requested_setting['key_file'] = module.params['key_file']

    # print differences if it is needed
    changed = dicts_are_different(current_setting, requested_setting)
    result['diff'] = {'before': current_setting, 'after': requested_setting}
    result['changed'] = changed

    # if it is in check mode, or it is not changed, exit
    if module.check_mode or not changed:
        module.exit_json(**result)
        return

    # when we change settings on an existing commitlog, we delete it and re-create
    if changed and found_settings:
        _, return_error = axonops.do_request(
            rel_url=commitlog_settings_url,
            method='DELETE',
            json_data=module.params['datacenters'],
        )

        if return_error:
            module.fail_json(msg=return_error, **result)

    if requested_setting['remote_type'] == 'local':
        remote_config_dict = {
            'type': requested_setting['remote_type']
        }
    elif requested_setting['remote_type'] == 's3':
        remote_config_dict = {
            'type': requested_setting['remote_type'],
            'provider': 'AWS',
            'region': requested_setting['s3_region'],
            'acl': requested_setting['s3_acl'],
            'server_side_encryption': requested_setting['s3_encryption'],
            'storage_class': requested_setting['s3_storage_class'],
            'disable_checksum': bool_to_string(requested_setting['s3_disable_checksum']),
        }

        if requested_setting['s3_secret_access_key'] and requested_setting['s3_access_key_id']:
            remote_config_dict['env_auth'] = 'false'
            remote_config_dict['access_key_id'] = requested_setting[
                's3_access_key_id'] if 's3_access_key_id' in requested_setting else module.params['s3_access_key_id']
            remote_config_dict['s3_secret_access_key'] = requested_setting[
                's3_secret_access_key'] if 's3_secret_access_key' in requested_setting else module.params[
                's3_secret_access_key']
        else:
            remote_config_dict['env_auth'] = 'true'

    elif requested_setting['remote_type'] == 'sftp':
        remote_config_dict = {
            'type': requested_setting['remote_type'],
            'host': requested_setting['host'],
            'ssh_user': requested_setting['ssh_user'],
            'ssh_pass': requested_setting['ssh_pass'] if 'ssh_pass' in requested_setting else module.params['ssh_pass'],
            'key_file': requested_setting['key_file'] if 'key_file' in requested_setting else '',
        }
    else:
        remote_config_dict = {}
        module.fail_json(msg=f"{requested_setting['remote_type']} is not a supported remote method", **result)

    remote_config = "\n".join([f"{k} = {v}" for k, v in remote_config_dict.items()])

    payload = {
        "remoteBackupsActive": False,
        "backupMethod": "Incremental",
        "timeout": requested_setting['timeout'],
        "bwlimit": requested_setting['bw_limit'],
        "localRetentionDuration": "",
        "remoteRetentionDuration": requested_setting['remote_retention'],
        "delegateRemoteRetention": False,
        "remoteType": requested_setting['remote_type'],
        "remotePath": requested_setting['remote_path'],
        "SFTPHost": requested_setting['host'] if 'host' in requested_setting else None,
        "SFTPUser": requested_setting['ssh_user'] if 'ssh_user' in requested_setting else None,
        "SFTPPass": requested_setting['ssh_pass'] if 'ssh_pass' in requested_setting else module.params['ssh_pass'],
        "SFTPPort": None,
        "SFTPKeyFile": requested_setting['key_file'] if 'key_file' in requested_setting else None,
        "AWSRegion": requested_setting['s3_region'] if 's3_region' in requested_setting else module.params['s3_region'],
        "AWSStorageClass": requested_setting['s3_storage_class'] if 's3_storage_class' in requested_setting else
        module.params['s3_storage_class'],
        "AWSAccessKeyId": requested_setting['s3_access_key_id'] if 's3_access_key_id' in requested_setting else
        module.params['s3_access_key_id'],
        "AWSSecretAccessKey": requested_setting[
            's3_secret_access_key'] if 's3_secret_access_key' in requested_setting else module.params[
            's3_secret_access_key'],
        "AWSACL": requested_setting['s3_acl'] if 's3_acl' in requested_setting else module.params['s3_acl'],
        "AWSServerSideEncryption": requested_setting['s3_encryption'] if 's3_encryption' in requested_setting else
        module.params['s3_encryption'],
        "AWSDisableChecksum": requested_setting[
            's3_disable_checksum'] if 's3_disable_checksum' in requested_setting else module.params[
            's3_disable_checksum'],
        "azureBlobAccount": "",
        "azureBlobKey": "",
        "azureBlobEndpoint": "",
        "azureBlobUseManagedServiceIdentity": False,
        "azureBlobMSIObjectID": "",
        "azureBlobMSIClientID": "",
        "azureBlobMSIResourceID": "",
        "GCSClientId": "",
        "GCSClientSecret": "",
        "GCSProjectNumber": "",
        "GCSServiceAccountCredentialsJSONFilePath": "",
        "GCSServiceAccountCredentialJSONBlob": "",
        "GCSBucketPolicyOnly": False,
        "GCSACLsObject": "",
        "GCSACLsBucket": "authenticatedRead",
        "GCSLocation": "eu",
        "GCSStorageClass": "",
        "S3CEndpoint": "",
        "S3CRegion": "",
        "datacenters": requested_setting['datacenters'],
        "remoteConfig": remote_config
    }

    result['payload'] = payload

    if requested_setting['present']:
        _, return_error = axonops.do_request(
            rel_url=commitlog_settings_url,
            method='POST',
            json_data=payload,
        )

        if return_error:
            module.fail_json(msg='POST' + return_error, **result)

    module.exit_json(**result)

def main():
    run_module()


if __name__ == '__main__':
    main()
