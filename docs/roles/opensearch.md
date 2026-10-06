# OpenSearch Role

## Overview

The `opensearch` role installs and configures OpenSearch on target nodes. It serves as the search and configuration backend for self-hosted AxonOps Server deployments. OpenSearch is the preferred search backend for on-premises deployments — it is fully open-source, ships with the Security plugin for TLS and authentication, and generates certificates automatically. The role supports both single-node development setups and multi-node production clusters.

## Requirements

- Ansible 2.10 or higher
- Target system running a supported Linux distribution (RHEL 8/9, Ubuntu, Debian)
- The `ansible.posix` collection (`ansible-galaxy collection install ansible.posix`)

## Role Variables

### Basic Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `opensearch_version` | `3.8.0` | OpenSearch version to install |
| `opensearch_arch` | derived from `ansible_architecture` | Bundle architecture: `x64` on x86_64 hosts, `arm64` on aarch64. Override only to force a specific bundle. |
| `opensearch_cluster_name` | `opensearch` | Cluster name |
| `opensearch_cluster_type` | `multi-node` | `single-node` or `multi-node` |
| `opensearch_install_root` | `/usr/share/opensearch` | Installation directory |
| `opensearch_user` | `opensearch` | System user |
| `opensearch_group` | `opensearch` | System group |

### Network

| Variable | Default | Description |
|----------|---------|-------------|
| `opensearch_api_port` | `9200` | HTTP API port |
| `opensearch_network_host` | `{{ ansible_default_ipv4.address }}` | Network bind address |
| `opensearch_bootstrap_memory_lock` | `true` | Lock memory to prevent swapping |

### JVM

| Variable | Default | Description |
|----------|---------|-------------|
| `opensearch_heap_size` | `1g` | JVM heap size (e.g. `1g`, `512m`) |
| `opensearch_tmp_dir` | `/var/lib/opensearch/tmp` | Temp directory for the JVM (`-Djava.io.tmpdir`) and the `OPENSEARCH_TMPDIR` environment variable in the systemd unit. Created by the role, owned by `opensearch:opensearch`, mode `0750`. Set to `""` to use the distribution defaults |

### Temp directory and `noexec` on `/tmp`

OpenSearch extracts native libraries at startup and cannot do so from a
filesystem mounted `noexec`. CIS-hardened builds and Amazon Linux 2023 mount
`/tmp` that way by default, which stops the service from starting.

The role points both the JVM and the surrounding shell environment at
`opensearch_tmp_dir`:

- `jvm.options` renders `-Djava.io.tmpdir={{ opensearch_tmp_dir }}` after the
  packaged `-Djava.io.tmpdir=${OPENSEARCH_TMPDIR}` line. The JVM applies the
  last `-D` for a property, so the role's value wins.
- The systemd unit renders `Environment=OPENSEARCH_TMPDIR={{ opensearch_tmp_dir }}`,
  so plugins, helper scripts and child processes that read `OPENSEARCH_TMPDIR`
  rather than `java.io.tmpdir` use the same directory.

The directory is created by the role, owned by `opensearch:opensearch`, with
mode `0750`.

`PrivateTmp=true` in the unit does **not** help here. A private `/tmp`
namespace inherits the mount options of its parent mount, so it does not clear
the `noexec` flag.

Set `opensearch_tmp_dir: ""` to disable the override entirely and fall back to
the distribution defaults. No directory is created in that case.

### Security

| Variable | Default | Description |
|----------|---------|-------------|
| `opensearch_security_enabled` | `true` | Enable the security plugin |
| `opensearch_admin_password` | — | **Required when security enabled.** Admin password |
| `opensearch_dashboards_password` | — | Dashboards/Kibana server password |
| `opensearch_auth_type` | `internal` | Auth type: `internal` or `oidc` |
| `opensearch_tls_mode` | `generate` | TLS mode: `generate` (self-signed) or `custom` (user-supplied) |

### TLS Generate Mode (`opensearch_tls_mode: generate`)

| Variable | Default | Description |
|----------|---------|-------------|
| `opensearch_cert_valid_days` | `730` | Certificate validity in days |
| `opensearch_domain_name` | — | Domain name for certificate DNs |
| `opensearch_tlstool_url` | Maven Central `search-guard-tlstool-1.5.tar.gz` | Download URL for `searchguard-tlstool` (override for an internal mirror) |
| `opensearch_tlstool_checksum` | `sha256:97efc3cb…` | Checksum of the tlstool archive; truncated downloads fail and are retried |
| `opensearch_tlstool_local_archive` | `""` | Pre-downloaded tlstool archive on the control node; skips the download, still checksum-verified |

### TLS Custom Mode (`opensearch_tls_mode: custom`)

All paths are on the **control node** and will be copied to each OpenSearch node.

| Variable | Description |
|----------|-------------|
| `opensearch_tls_root_ca` | Path to root CA certificate (PEM) |
| `opensearch_tls_root_ca_key` | Path to root CA private key |
| `opensearch_tls_admin_cert` | Path to admin client certificate |
| `opensearch_tls_admin_key` | Path to admin client private key |
| `opensearch_tls_node_cert` | Path to node transport certificate (supports `{{ inventory_hostname }}`) |
| `opensearch_tls_node_key` | Path to node transport private key |
| `opensearch_tls_node_http_cert` | Path to node HTTP certificate |
| `opensearch_tls_node_http_key` | Path to node HTTP private key |
| `opensearch_tls_admin_dn` | Admin certificate DN (for `plugins.security.authcz.admin_dn`) |
| `opensearch_tls_node_dn` | Node certificate DN pattern (for `plugins.security.nodes_dn`) |

### System Tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `opensearch_vm_max_map_count` | `262144` | `vm.max_map_count` sysctl value |
| `opensearch_fs_file_max` | `65536` | `fs.file-max` sysctl value |

### Snapshot Repositories (S3/GCS)

| Variable | Type | Default | Example | Description |
|----------|------|---------|---------|-------------|
| `opensearch_snapshot_enabled` | bool | `false` | `true` | Install the repository plugin, load credentials and register the repository |
| `opensearch_snapshot_type` | string | `s3` | `gcs` | Backend: `s3` (AWS S3 or any S3-compatible store) or `gcs` |
| `opensearch_snapshot_client` | string | `default` | `backups` | Client name used in the `s3.client.<client>.*` / `gcs.client.<client>.*` settings |
| `opensearch_snapshot_repository_name` | string | `<type>-snapshots` | `nightly` | Snapshot repository name |
| `opensearch_snapshot_bucket` | string | `""` | `opensearch-backups` | Bucket name. Required |
| `opensearch_snapshot_base_path` | string | `""` | `prod/cluster1` | Path prefix inside the bucket |
| `opensearch_snapshot_plugin_local_archive` | string | `""` | `/srv/plugins/repository-s3-3.8.0.zip` | Plugin zip on the control node, for hosts that cannot reach `artifacts.opensearch.org`. Must match `opensearch_version` |
| `opensearch_snapshot_s3_access_key` | string | `""` | `"{{ vault_s3_access_key }}"` | Static access key. Set together with the secret key |
| `opensearch_snapshot_s3_secret_key` | string | `""` | `"{{ vault_s3_secret_key }}"` | Static secret key |
| `opensearch_snapshot_s3_session_token` | string | `""` | `"{{ vault_s3_session_token }}"` | Optional session token for temporary credentials |
| `opensearch_snapshot_s3_region` | string | `""` | `eu-west-1`, `fsn1` | Signing region |
| `opensearch_snapshot_s3_endpoint` | string | `""` | `fsn1.your-objectstorage.com` | Endpoint for S3-compatible stores (Hetzner Object Storage, MinIO, Ceph RGW) |
| `opensearch_snapshot_s3_protocol` | string | `""` | `http` | `http` or `https`. Empty keeps the plugin default (`https`) |
| `opensearch_snapshot_s3_path_style_access` | bool | `false` | `true` | Use path-style URLs (`https://endpoint/bucket`) instead of virtual-hosted style |
| `opensearch_snapshot_s3_extra_settings` | dict | `{}` | `{disable_chunked_encoding: true}` | Other non-secret `s3.client.<client>.*` settings, for S3-compatible stores that need them (`signer_override`, `disable_chunked_encoding`, `legacy_md5_checksum_calculation`, timeouts) |
| `opensearch_snapshot_gcs_credentials_json` | string or mapping | `""` | `"{{ vault_gcs_sa_json }}"` | Service-account JSON |
| `opensearch_snapshot_gcs_project_id` | string | `""` | `my-project` | GCP project ID |
| `opensearch_snapshot_gcs_endpoint` | string | `""` | `https://storage.example.com` | Custom GCS endpoint |
| `opensearch_snapshot_policy` | dict | `{}` | see below | Snapshot Management policy. `name` is the policy name; the other keys are the `_plugins/_sm/policies` request body. `snapshot_config.repository` defaults to the repository name |

Credentials are written only to `opensearch.keystore` (owner `opensearch_user`, mode `0640`); they never appear in `opensearch.yml` or the Ansible output. Region, endpoint, protocol, path-style and project settings go into `opensearch.yml`.

The keystore is created without a password, so it is obfuscated rather than encrypted: protect it with file permissions and keep the source credentials in ansible-vault.

Leave the static credentials empty to use the instance identity instead: an EC2 instance profile or IRSA for S3, or GCE/GKE workload identity for GCS. The role then removes any credentials it previously stored for that client.

Installing the plugin or changing credentials restarts OpenSearch on every node at the same time. The repository and policy are registered once per cluster, and only when `opensearch_start_on_install` is `true`. Restoring snapshots is not automated.

Setting `opensearch_snapshot_enabled: false` later does not remove the plugin, the repository or the keystore credentials. Removing a key from `opensearch_snapshot_policy` does not remove it from an existing policy; delete the policy (`DELETE _plugins/_sm/policies/<name>`) and re-run the role.

### Service

| Variable | Default | Description |
|----------|---------|-------------|
| `opensearch_start_on_boot` | `true` | Enable service at boot |
| `opensearch_start_on_install` | `true` | Start service after installation |
| `opensearch_populate_etc_hosts` | `true` | Populate /etc/hosts with cluster nodes |
| `opensearch_iac_enable` | `false` | IaC mode for idempotent re-runs |

## Example Playbooks

### Single-Node (Development)

```yaml
- name: Deploy single-node OpenSearch
  hosts: opensearch
  become: true

  vars:
    opensearch_version: "3.8.0"
    opensearch_cluster_name: axonops-dev
    opensearch_cluster_type: single-node
    opensearch_heap_size: "1g"
    opensearch_admin_password: "{{ vault_opensearch_admin_password }}"
    opensearch_domain_name: example.com

  roles:
    - axonops.axonops.opensearch
```

### Multi-Node Cluster

```yaml
- name: Deploy OpenSearch cluster
  hosts: opensearch
  become: true

  vars:
    opensearch_version: "3.8.0"
    opensearch_cluster_name: axonops-production
    opensearch_cluster_type: multi-node
    opensearch_heap_size: "4g"
    opensearch_admin_password: "{{ vault_opensearch_admin_password }}"
    opensearch_dashboards_password: "{{ vault_opensearch_dashboards_password }}"
    opensearch_domain_name: example.com

  roles:
    - axonops.axonops.opensearch
```

### Custom TLS Certificates

```yaml
- name: Deploy OpenSearch with custom certificates
  hosts: opensearch
  become: true

  vars:
    opensearch_cluster_name: axonops-production
    opensearch_cluster_type: multi-node
    opensearch_heap_size: "4g"
    opensearch_admin_password: "{{ vault_opensearch_admin_password }}"
    opensearch_tls_mode: custom
    opensearch_tls_root_ca: /path/to/certs/root-ca.pem
    opensearch_tls_root_ca_key: /path/to/certs/root-ca.key
    opensearch_tls_admin_cert: /path/to/certs/admin.pem
    opensearch_tls_admin_key: /path/to/certs/admin.key
    opensearch_tls_node_cert: "/path/to/certs/{{ inventory_hostname }}.pem"
    opensearch_tls_node_key: "/path/to/certs/{{ inventory_hostname }}.key"
    opensearch_tls_node_http_cert: "/path/to/certs/{{ inventory_hostname }}_http.pem"
    opensearch_tls_node_http_key: "/path/to/certs/{{ inventory_hostname }}_http.key"
    opensearch_tls_admin_dn: "CN=admin,OU=Ops,O=My Company,DC=example.com"
    opensearch_tls_node_dn: "CN=*.example.com,OU=Ops,O=My Company,DC=example.com"

  roles:
    - axonops.axonops.opensearch
```

### Without Security Plugin

```yaml
- name: Deploy OpenSearch without security
  hosts: opensearch
  become: true

  vars:
    opensearch_cluster_name: axonops-test
    opensearch_cluster_type: single-node
    opensearch_security_enabled: false

  roles:
    - axonops.axonops.opensearch
```

### Part of Self-Hosted AxonOps Stack

Deploy OpenSearch alongside AxonOps Server and Dashboard on a single host. The `axon_server_searchdb_*`
variables connect axon-server to OpenSearch. When using auto-generated certificates
(`opensearch_tls_mode: generate`), set `axon_server_searchdb_tls_skip_verify: true` so that axon-server
accepts the self-signed certificates.

```yaml
- name: Deploy AxonOps Server with OpenSearch
  hosts: axon-server
  become: true

  vars:
    # OpenSearch
    opensearch_cluster_name: axonops
    opensearch_cluster_type: single-node
    opensearch_admin_password: "{{ vault_opensearch_admin_password }}"
    opensearch_domain_name: example.com

    # AxonOps Server search_db connection
    axon_server_license_key: "{{ vault_axonops_license_key }}"
    axon_server_searchdb_hosts:
      - "https://127.0.0.1:9200"
    axon_server_searchdb_username: admin
    axon_server_searchdb_password: "{{ vault_opensearch_admin_password }}"
    axon_server_searchdb_tls_skip_verify: true

  roles:
    - axonops.axonops.opensearch
    - axonops.axonops.server
    - axonops.axonops.dash
```

### S3 Snapshot Backups

Works with AWS S3 and with S3-compatible stores. The example below uses Hetzner Object Storage; for AWS, drop the endpoint and path-style settings and set the AWS region.

```yaml
- name: Deploy OpenSearch with S3 snapshots
  hosts: opensearch
  become: true

  vars:
    opensearch_cluster_name: axonops-production
    opensearch_admin_password: "{{ vault_opensearch_admin_password }}"
    opensearch_domain_name: example.com
    opensearch_snapshot_enabled: true
    opensearch_snapshot_type: s3
    opensearch_snapshot_bucket: opensearch-backups
    opensearch_snapshot_base_path: axonops-production
    opensearch_snapshot_s3_access_key: "{{ vault_s3_access_key }}"
    opensearch_snapshot_s3_secret_key: "{{ vault_s3_secret_key }}"
    opensearch_snapshot_s3_region: fsn1
    opensearch_snapshot_s3_endpoint: fsn1.your-objectstorage.com
    opensearch_snapshot_s3_path_style_access: true
    opensearch_snapshot_policy:
      name: daily
      creation:
        schedule:
          cron:
            expression: "0 2 * * *"
            timezone: UTC
      deletion:
        schedule:
          cron:
            expression: "0 3 * * *"
            timezone: UTC
        condition:
          max_age: 14d
          min_count: 1
      snapshot_config:
        indices: "*"

  roles:
    - axonops.axonops.opensearch
```

Check the repository after the run:

```bash
curl -k -u admin:<password> -X POST https://<node>:9200/_snapshot/s3-snapshots/_verify
```

## Tags

| Tag | Description |
|-----|-------------|
| `hosts` | /etc/hosts population |
| `tune` | System tuning (sysctl) |
| `install` | OpenSearch download and installation |
| `security` | Security plugin configuration |
| `health` | Cluster health check |
| `snapshot` | Snapshot plugin, keystore credentials, repository and policy |

## Notes

- **Security plugin**: When enabled, the role generates self-signed TLS certificates using the searchguard-tlstool on the control node and distributes them to cluster nodes.
- **Inventory group**: Multi-node clusters expect hosts to be in the `opensearch` inventory group.
- **Memory lock**: `opensearch_bootstrap_memory_lock` is enabled by default to prevent JVM heap swapping. Ensure the systemd service has `LimitMEMLOCK=infinity`.
- **IaC mode**: Set `opensearch_iac_enable: true` for idempotent re-runs that check certificate state and regenerate if needed.

## License

See the main collection LICENSE file.

## Author

AxonOps Limited
