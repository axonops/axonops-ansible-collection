# OpenSearch Role

## Overview

The `opensearch` role installs and configures OpenSearch on target nodes. It serves as the backend configuration and metrics store for self-hosted AxonOps Server deployments. The role supports both single-node development setups and multi-node production clusters, with full TLS security via the OpenSearch Security plugin. Certificates can be generated automatically or supplied from your own PKI.

**Note**: This role is only needed for self-hosted AxonOps deployments. AxonOps SaaS users do not need to install or manage OpenSearch.

## Requirements

- Ansible 2.10 or higher
- `ansible.posix` collection (`ansible-galaxy collection install ansible.posix`)
- Target nodes running a supported Linux distribution:
  - RHEL / AlmaLinux / Rocky Linux 8 or 9
  - Ubuntu (all supported releases)
  - Debian (all supported releases)
- The control node requires Java (JRE) if using `opensearch_tls_mode: generate`, as the certificate generation tool (`searchguard-tlstool`) is executed locally

## Role Variables

### Installation

| Variable | Default | Description |
|----------|---------|-------------|
| `opensearch_version` | `3.6.0` | OpenSearch version to install |
| `opensearch_download_url` | `https://artifacts.opensearch.org/releases/bundle/opensearch` | Base URL for the OpenSearch tar.gz download |
| `opensearch_install_root` | `/usr/share/opensearch` | Directory where OpenSearch is extracted |
| `opensearch_conf_dir` | `{{ opensearch_install_root }}/config` | Configuration directory |
| `opensearch_user` | `opensearch` | System user that runs the OpenSearch process |
| `opensearch_group` | `opensearch` | System group for the OpenSearch process |

### Cluster Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `opensearch_cluster_name` | `opensearch` | Name of the OpenSearch cluster. Change this for every deployment — the role warns if you leave the default |
| `opensearch_cluster_type` | `multi-node` | Topology mode: `single-node` or `multi-node` |
| `opensearch_seed_hosts` | All hosts in the current play | List of hostnames or IPs used for node discovery (multi-node only). Defaults to all hosts in the current play |
| `opensearch_initial_master_nodes` | All hosts in the current play | List of master-eligible node names for initial cluster bootstrap (multi-node only). Removed automatically after the cluster forms |
| `opensearch_node_roles` | _(not set)_ | Comma-separated list of node roles (e.g. `cluster_manager, data, ingest`). When not set, the node takes all roles. Set per host in inventory |

### Network

| Variable | Default | Description |
|----------|---------|-------------|
| `opensearch_api_port` | `9200` | HTTP API port |
| `opensearch_network_host` | `{{ ansible_default_ipv4.address }}` | IP address or hostname OpenSearch binds to. Falls back to `0.0.0.0` when no default IPv4 address is detected |
| `opensearch_bootstrap_memory_lock` | `true` | Lock JVM heap in RAM to prevent swapping. Requires `LimitMEMLOCK=infinity` in the systemd unit, which this role sets automatically |

### JVM

| Variable | Default | Description |
|----------|---------|-------------|
| `opensearch_heap_size` | `1g` | JVM heap size. Applied to both `-Xms` and `-Xmx`. Use `g` for gigabytes or `m` for megabytes (e.g. `4g`, `512m`). As a rule of thumb, set this to no more than half of available RAM |
| `opensearch_tmp_dir` | _(not set)_ | Custom temporary directory for the JVM. Set this when `/tmp` is mounted with `noexec`, which prevents OpenSearch from starting |

### Security Plugin

| Variable | Default | Description |
|----------|---------|-------------|
| `opensearch_security_enabled` | `true` | Enable the OpenSearch Security plugin. When set to `false`, the cluster runs without TLS or authentication |
| `opensearch_admin_password` | _(required)_ | Password for the built-in `admin` user. Required when `opensearch_security_enabled` is `true`. Store with Ansible Vault |
| `opensearch_dashboards_password` | _(not set)_ | Password for the built-in `kibanaserver` user, used by OpenSearch Dashboards. Falls back to `opensearch_admin_password` when not set |
| `opensearch_auth_type` | `internal` | Authentication type: `internal` (username/password against local user database) or `oidc` (OpenID Connect) |

### TLS Mode

| Variable | Default | Description |
|----------|---------|-------------|
| `opensearch_tls_mode` | `generate` | How TLS certificates are provisioned: `generate` (self-signed, automatic) or `custom` (user-supplied from control node) |

#### TLS: `generate` mode

In `generate` mode, the role downloads and runs the `searchguard-tlstool` on the control node to create a root CA, per-node transport certificates, per-node HTTP certificates, and an admin client certificate. These are then distributed to each node. No manual certificate management is required.

| Variable | Default | Description |
|----------|---------|-------------|
| `opensearch_cert_valid_days` | `730` | Number of days the generated certificates remain valid |
| `opensearch_domain_name` | _(not set)_ | Domain suffix used in certificate Distinguished Names and DNS SANs (e.g. `example.com`). Required in generate mode |

#### TLS: `custom` mode

In `custom` mode, you supply all certificates yourself. The role copies them from the control node to each OpenSearch node. All variables in this section are required when `opensearch_tls_mode` is set to `custom`.

Certificate path values support Jinja2 expressions, which lets you reference per-host files using `{{ inventory_hostname }}`.

| Variable | Description |
|----------|-------------|
| `opensearch_tls_root_ca` | Path on the control node to the root CA certificate (PEM format) |
| `opensearch_tls_root_ca_key` | Path on the control node to the root CA private key |
| `opensearch_tls_admin_cert` | Path on the control node to the admin client certificate |
| `opensearch_tls_admin_key` | Path on the control node to the admin client private key |
| `opensearch_tls_node_cert` | Path on the control node to each node's transport certificate. Supports `{{ inventory_hostname }}` |
| `opensearch_tls_node_key` | Path on the control node to each node's transport private key. Supports `{{ inventory_hostname }}` |
| `opensearch_tls_node_http_cert` | Path on the control node to each node's HTTP (REST API) certificate. Supports `{{ inventory_hostname }}` |
| `opensearch_tls_node_http_key` | Path on the control node to each node's HTTP private key. Supports `{{ inventory_hostname }}` |
| `opensearch_tls_admin_dn` | Full Distinguished Name of the admin certificate, written to `plugins.security.authcz.admin_dn` in `opensearch.yml`. Example: `CN=admin,OU=Ops,O=Example Inc.,DC=example,DC=com` |
| `opensearch_tls_node_dn` | DN pattern that matches all node certificates, written to `plugins.security.nodes_dn`. Example: `CN=*.example.com,OU=Ops,O=Example Inc.,DC=example,DC=com` |

### Custom Security Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `opensearch_custom_security_configs` | `[]` | List of Jinja2 template paths (relative to your playbook) to deploy into the `opensearch-security` configuration directory. Use this to supply custom `roles.yml`, `roles_mapping.yml`, and similar files |
| `opensearch_copy_custom_security_configs` | `false` | When `true`, deploys the templates listed in `opensearch_custom_security_configs` and reinitialises the security index using `securityadmin.sh` |

### OIDC Authentication

These variables apply when `opensearch_auth_type` is set to `oidc`.

| Variable | Description |
|----------|-------------|
| `opensearch_oidc.subject_key` | JWT claim to use as the username (e.g. `preferred_username`) |
| `opensearch_oidc.roles_key` | JWT claim to use for role mapping (e.g. `roles`) |
| `opensearch_oidc.connect_url` | OpenID Connect discovery endpoint URL |
| `opensearch_oidc.dashboards_url` | Public URL of OpenSearch Dashboards, used for OIDC redirects |

Example:

```yaml
opensearch_oidc:
  subject_key: preferred_username
  roles_key: roles
  connect_url: https://idp.example.com/.well-known/openid-configuration
  dashboards_url: https://dashboards.example.com
```

### System Tuning

The role applies the following kernel and system settings to every target node. All values are configurable.

| Variable | Default | Kernel parameter | Purpose |
|----------|---------|-----------------|---------|
| `opensearch_vm_max_map_count` | `262144` | `vm.max_map_count` | Required by OpenSearch for memory-mapped files. The default Linux value of `65530` is too low and prevents startup |
| `opensearch_fs_file_max` | `65536` | `fs.file-max` | Maximum number of open file descriptors system-wide |
| `opensearch_vm_swappiness` | `1` | `vm.swappiness` | Reduces the kernel's tendency to swap memory. A value of `1` is preferred over `0` to avoid OOM in edge cases |
| `opensearch_tcp_retries2` | `5` | `net.ipv4.tcp_retries2` | Reduces TCP timeout for failed connections between cluster nodes |
| `opensearch_disable_thp` | `true` | THP kernel subsystem | Disables Transparent Huge Pages for the current boot session and installs a `disable-thp` systemd service to persist across reboots. THP causes JVM performance problems and is not recommended for any JVM workload |

The systemd service unit also sets these resource limits regardless of tuning variables:

- `LimitNOFILE=65536` — maximum open file descriptors per process
- `LimitMEMLOCK=infinity` — required for `bootstrap.memory_lock: true`
- `LimitNPROC=4096` — maximum threads
- `LimitAS=infinity` — no virtual memory cap
- `LimitFSIZE=infinity` — no file size cap

### `/etc/hosts` Management

| Variable | Default | Description |
|----------|---------|-------------|
| `opensearch_populate_etc_hosts` | `true` | Add all hosts from the current play to `/etc/hosts` on each node. Useful when DNS is not available or not yet configured for cluster hostnames |
| `opensearch_domain_name` | _(not set)_ | Domain suffix appended to hostnames when writing `/etc/hosts` entries. Entries take the form `<ip> <hostname>.<domain> <hostname>` |

### Service Management

| Variable | Default | Description |
|----------|---------|-------------|
| `opensearch_start_on_boot` | `true` | Enable the `opensearch` systemd service to start automatically at boot |
| `opensearch_start_on_install` | `true` | Start OpenSearch immediately after the role finishes. When `false`, the service is configured but not started |

### IaC Mode

| Variable | Default | Description |
|----------|---------|-------------|
| `opensearch_iac_enable` | `false` | Enable Infrastructure-as-Code mode. When `true`, the role checks whether certificates exist on each node and regenerates them if any are missing. Also forces security index reinitialisation. Use this for pipelines that run the role repeatedly against existing clusters |

## Tags

Use tags to run only specific parts of the role:

| Tag | Tasks performed |
|-----|----------------|
| `hosts` | Populate `/etc/hosts` with cluster node entries |
| `tune` | Apply sysctl settings and Transparent Huge Pages configuration |
| `install` | Download, extract, and configure OpenSearch and its systemd unit |
| `security` | Configure the Security plugin, generate or deploy TLS certificates, and initialise the security index |
| `service` | Start the OpenSearch service and wait for it to become available |
| `health` | Query the cluster health API and display the result |

Example — run only system tuning and installation:

```bash
ansible-playbook site.yml --tags tune,install
```

Example — skip the health check:

```bash
ansible-playbook site.yml --skip-tags health
```

## Dependencies

This role has no hard Ansible role dependencies. It does require the `ansible.posix` collection for the `sysctl` module used in system tuning:

```bash
ansible-galaxy collection install ansible.posix
```

When used as part of the full AxonOps stack, deploy this role before the `axonops.axonops.server` role.

## Example Playbooks

### Single-Node Development Cluster

The simplest configuration for local development or evaluation. Uses automatic certificate generation.

```yaml
- name: Deploy single-node OpenSearch
  hosts: opensearch
  become: true

  vars:
    opensearch_cluster_name: axonops-dev
    opensearch_cluster_type: single-node
    opensearch_heap_size: "1g"
    opensearch_admin_password: "{{ vault_opensearch_admin_password }}"
    opensearch_domain_name: example.com

  roles:
    - axonops.axonops.opensearch
```

### Multi-Node Production Cluster

A three-node cluster with automatically generated certificates. All nodes run the role in a single play, which causes the role to include all three in discovery and certificate generation automatically.

```yaml
- name: Deploy OpenSearch cluster
  hosts: opensearch
  become: true

  vars:
    opensearch_cluster_name: axonops-production
    opensearch_cluster_type: multi-node
    opensearch_heap_size: "8g"
    opensearch_admin_password: "{{ vault_opensearch_admin_password }}"
    opensearch_dashboards_password: "{{ vault_opensearch_dashboards_password }}"
    opensearch_domain_name: internal.example.com
    opensearch_cert_valid_days: 1095

  roles:
    - axonops.axonops.opensearch
```

Inventory for the above playbook:

```ini
[opensearch]
os-node-1.internal.example.com
os-node-2.internal.example.com
os-node-3.internal.example.com
```

### Multi-Node Cluster with Dedicated Roles

Use `opensearch_node_roles` in your inventory to separate cluster manager, data, and ingest responsibilities across nodes.

```ini
[opensearch]
os-manager-1.example.com opensearch_node_roles="cluster_manager"
os-manager-2.example.com opensearch_node_roles="cluster_manager"
os-manager-3.example.com opensearch_node_roles="cluster_manager"
os-data-1.example.com    opensearch_node_roles="data, ingest"
os-data-2.example.com    opensearch_node_roles="data, ingest"
```

```yaml
- name: Deploy OpenSearch with dedicated node roles
  hosts: opensearch
  become: true

  vars:
    opensearch_cluster_name: axonops-production
    opensearch_cluster_type: multi-node
    opensearch_heap_size: "16g"
    opensearch_admin_password: "{{ vault_opensearch_admin_password }}"
    opensearch_domain_name: example.com

  roles:
    - axonops.axonops.opensearch
```

### Custom TLS Certificates

Use certificates issued by your own CA instead of auto-generated self-signed certificates. All certificate files must exist on the control node before the play runs.

```yaml
- name: Deploy OpenSearch with custom TLS certificates
  hosts: opensearch
  become: true

  vars:
    opensearch_cluster_name: axonops-production
    opensearch_cluster_type: multi-node
    opensearch_heap_size: "8g"
    opensearch_admin_password: "{{ vault_opensearch_admin_password }}"
    opensearch_tls_mode: custom
    opensearch_tls_root_ca: /etc/pki/tls/opensearch/root-ca.pem
    opensearch_tls_root_ca_key: /etc/pki/tls/opensearch/root-ca.key
    opensearch_tls_admin_cert: /etc/pki/tls/opensearch/admin.pem
    opensearch_tls_admin_key: /etc/pki/tls/opensearch/admin.key
    # The inventory_hostname expression selects the correct file per node
    opensearch_tls_node_cert: "/etc/pki/tls/opensearch/{{ inventory_hostname }}.pem"
    opensearch_tls_node_key: "/etc/pki/tls/opensearch/{{ inventory_hostname }}.key"
    opensearch_tls_node_http_cert: "/etc/pki/tls/opensearch/{{ inventory_hostname }}_http.pem"
    opensearch_tls_node_http_key: "/etc/pki/tls/opensearch/{{ inventory_hostname }}_http.key"
    opensearch_tls_admin_dn: "CN=admin,OU=Ops,O=My Company,DC=example,DC=com"
    opensearch_tls_node_dn: "CN=*.example.com,OU=Ops,O=My Company,DC=example,DC=com"

  roles:
    - axonops.axonops.opensearch
```

### Without Security (Development Only)

Disables the Security plugin entirely. The cluster is accessible over plain HTTP with no authentication. **Do not use this in production.**

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

### As Part of the Self-Hosted AxonOps Stack

Deploy OpenSearch alongside AxonOps Server and Dashboard in a single play. The role order matters: OpenSearch must be running before the server role starts.

```yaml
- name: Deploy self-hosted AxonOps stack
  hosts: axonops_server
  become: true

  vars:
    # OpenSearch
    opensearch_cluster_name: axonops
    opensearch_cluster_type: single-node
    opensearch_admin_password: "{{ vault_opensearch_admin_password }}"
    opensearch_domain_name: example.com

    # AxonOps Server
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

### OIDC Authentication

Authenticate users against an external OpenID Connect provider such as Keycloak, Okta, or Azure AD.

```yaml
- name: Deploy OpenSearch with OIDC authentication
  hosts: opensearch
  become: true

  vars:
    opensearch_cluster_name: axonops-production
    opensearch_cluster_type: multi-node
    opensearch_heap_size: "8g"
    opensearch_admin_password: "{{ vault_opensearch_admin_password }}"
    opensearch_domain_name: example.com
    opensearch_auth_type: oidc
    opensearch_oidc:
      subject_key: preferred_username
      roles_key: roles
      connect_url: https://idp.example.com/auth/realms/axonops/.well-known/openid-configuration
      dashboards_url: https://dashboards.example.com

  roles:
    - axonops.axonops.opensearch
```

### IaC Pipeline (Idempotent Re-runs)

Enable `opensearch_iac_enable` when running the role from a CI/CD pipeline or applying it to a running cluster. The role checks whether certificates are present on each node and only regenerates or re-applies configuration when necessary.

```yaml
- name: Reconcile OpenSearch cluster state
  hosts: opensearch
  become: true

  vars:
    opensearch_cluster_name: axonops-production
    opensearch_cluster_type: multi-node
    opensearch_heap_size: "8g"
    opensearch_admin_password: "{{ vault_opensearch_admin_password }}"
    opensearch_domain_name: example.com
    opensearch_iac_enable: true

  roles:
    - axonops.axonops.opensearch
```

### Custom /tmp Directory

If `/tmp` is mounted with `noexec` on your hosts, OpenSearch cannot extract its native libraries there and will fail to start. Set `opensearch_tmp_dir` to a directory on a `exec`-capable filesystem.

```yaml
- name: Deploy OpenSearch with custom temp directory
  hosts: opensearch
  become: true

  vars:
    opensearch_cluster_name: axonops-production
    opensearch_cluster_type: multi-node
    opensearch_admin_password: "{{ vault_opensearch_admin_password }}"
    opensearch_domain_name: example.com
    opensearch_tmp_dir: /var/lib/opensearch/tmp

  roles:
    - axonops.axonops.opensearch
```

## How TLS Works

### Generate Mode (default)

1. The role downloads `searchguard-tlstool` to `/tmp/opensearch-nodecerts/` on the **control node** (once, using `run_once`).
2. A TLS configuration template is rendered that includes every node in the play with its hostname, FQDN, and IP address.
3. The tool generates a root CA, per-node transport certificates (separate from HTTP certificates), and an admin client certificate.
4. All generated certificates are copied to `{{ opensearch_conf_dir }}/` on each node.
5. The tool also produces an `opensearch.yml` snippet for each node, which the role appends to the main configuration file.
6. The `securityadmin.sh` script runs on one node to initialise the security index with the hashed user passwords.
7. The local temporary directory is cleaned up after distribution.

The generated certificates are created only once per cluster setup. To force regeneration on an existing cluster, set `opensearch_iac_enable: true`.

### Custom Mode

1. The role validates that all required certificate path variables are defined. The play fails immediately if any are missing.
2. Each certificate is copied from the control node to `{{ opensearch_conf_dir }}/` on the corresponding target node.
3. A TLS configuration block is appended to `opensearch.yml` referencing the deployed certificate files and the DN values you provided.
4. The security index is initialised as in generate mode.

## Post-Installation Verification

After the role completes, verify the cluster is healthy:

```bash
# With security enabled
curl -k -u admin:your_password \
  https://<node-ip>:9200/_cluster/health?pretty

# Without security
curl http://<node-ip>:9200/_cluster/health?pretty
```

Check the service status and logs:

```bash
systemctl status opensearch
journalctl -u opensearch -f
```

For a multi-node cluster, confirm all nodes have joined:

```bash
curl -k -u admin:your_password \
  https://<node-ip>:9200/_cat/nodes?v
```

## Notes

- **Cluster name warning**: The role issues a warning (but does not fail) when `opensearch_cluster_name` is left at the default value `opensearch`. Always set a meaningful cluster name for production deployments.

- **Memory lock**: `opensearch_bootstrap_memory_lock` is enabled by default. The systemd service unit sets `LimitMEMLOCK=infinity` automatically, so no additional configuration is needed on the host.

- **Multi-node bootstrap**: The role adds `cluster.initial_master_nodes` to `opensearch.yml` during initial bootstrap and then removes it once the cluster has formed. This follows the OpenSearch recommendation to avoid split-brain during restarts after the cluster is established.

- **Password hashing**: The role hashes `opensearch_admin_password` and `opensearch_dashboards_password` using the `hash.sh` utility bundled with OpenSearch. Plain-text passwords are never written to configuration files.

- **Custom internal users**: If a `files/internal_users.yml` file exists relative to your playbook, the role detects it and hashes passwords for any additional users defined there. Each user must have a corresponding `<username>_password` variable in scope.

- **Security index initialisation**: The `securityadmin.sh` script runs with `-nhnv` (no hostname verification) and `-icl` (ignore cluster leader). It runs on one node only (`run_once`). If the cluster is not yet fully formed when this runs, OpenSearch retries internally. Allow up to two minutes for the cluster to become available.

- **`/etc/hosts` population**: When `opensearch_populate_etc_hosts` is `true`, the role writes entries for every host in the current play to `/etc/hosts`. Entries are idempotent and managed within a marked block, so re-running the role safely updates them.

- **Supported architecture**: The role downloads the `linux-x64` (AMD64) tarball. ARM64 nodes are not currently supported.

## License

See the main collection `LICENSE` file.

## Author

AxonOps Limited
