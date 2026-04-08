# OpenSearch Role

## Overview

The `opensearch` role installs and configures OpenSearch on target nodes. It is used as the backend configuration store for self-hosted AxonOps Server deployments, replacing Elasticsearch. It supports both single-node and multi-node cluster configurations with optional TLS security.

## Requirements

- Ansible 2.10 or higher
- Target system running a supported Linux distribution (RHEL 8/9, Ubuntu, Debian)
- The `ansible.posix` collection (`ansible-galaxy collection install ansible.posix`)

## Role Variables

### Basic Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `opensearch_version` | `3.0.0` | OpenSearch version to install |
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
| `opensearch_tmp_dir` | — | Custom temp directory (for noexec /tmp) |

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
    opensearch_version: "3.0.0"
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
    opensearch_version: "3.0.0"
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

```yaml
- name: Deploy AxonOps Server with OpenSearch
  hosts: axon-server
  become: true

  vars:
    opensearch_cluster_name: axonops
    opensearch_cluster_type: single-node
    opensearch_admin_password: "{{ vault_opensearch_admin_password }}"
    opensearch_domain_name: example.com

  roles:
    - axonops.axonops.opensearch
    - axonops.axonops.server
    - axonops.axonops.dash
```

## Tags

| Tag | Description |
|-----|-------------|
| `hosts` | /etc/hosts population |
| `tune` | System tuning (sysctl) |
| `install` | OpenSearch download and installation |
| `security` | Security plugin configuration |
| `health` | Cluster health check |

## Notes

- **Security plugin**: When enabled, the role generates self-signed TLS certificates using the searchguard-tlstool on the control node and distributes them to cluster nodes.
- **Inventory group**: Multi-node clusters expect hosts to be in the `opensearch` inventory group.
- **Memory lock**: `opensearch_bootstrap_memory_lock` is enabled by default to prevent JVM heap swapping. Ensure the systemd service has `LimitMEMLOCK=infinity`.
- **IaC mode**: Set `opensearch_iac_enable: true` for idempotent re-runs that check certificate state and regenerate if needed.

## License

See the main collection LICENSE file.

## Author

AxonOps Limited
