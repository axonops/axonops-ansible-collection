# AxonOps Server Role

## Overview

The `server` role installs and configures the AxonOps Server, which is the core component for monitoring and managing Cassandra clusters. The AxonOps Server aggregates metrics, handles alerts, manages backups, and provides the API for the AxonOps Dashboard.

**Note**: This role is only needed for self-hosted deployments. If you're using AxonOps SaaS, you only need the `agent` role on your Cassandra nodes.

## Requirements

- Ansible 2.9 or higher
- Target system running a supported Linux distribution (RHEL, CentOS, Ubuntu, Debian)
- Elasticsearch installed and running (use the `elastic` role)
- Cassandra installed for metrics storage (optional but recommended, use the `cassandra` role)
- Sufficient system resources (minimum 4GB RAM, 20GB disk space)

## Role Variables

### Basic Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `axon_server_state` | `present` | State of the server: `present` or `absent` |
| `axon_server_version` | `latest` | Version of AxonOps Server to install |
| `axon_server_hum` | `false` | Enable Human Readable IDs |

### Network Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `axon_server_listen_address` | `0.0.0.0` | IP address the server listens on |
| `axon_server_listen_port` | `8080` | Port the server listens on |

### Elasticsearch Configuration

**For AxonOps Server >= 2.0.4** (new syntax):

| Variable | Default | Description |
|----------|---------|-------------|
| `axon_server_elastic_hosts` | `["http://127.0.0.1:9200"]` | Array of Elasticsearch host URLs |
| `axon_server_elastic_shards` | `1` | Number of shards for indices |
| `axon_server_elastic_replicas` | `0` | Number of replicas for indices |
| `axon_server_elastic_tls_skip_verify` | `false` | Skip TLS certificate verification |
| `axon_server_elastic_username` | - | Elasticsearch username (if auth enabled) |
| `axon_server_elastic_password` | - | Elasticsearch password (if auth enabled) |

**For older versions** (legacy syntax):

| Variable | Default | Description |
|----------|---------|-------------|
| `axon_server_elastic_host` | `http://127.0.0.1` | Elasticsearch host URL |
| `axon_server_elastic_port` | `9200` | Elasticsearch port |

### Cassandra Storage Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `axon_server_cql_hosts` | `[]` | Array of Cassandra CQL endpoints (e.g., `["localhost:9042"]`) |
| `axon_server_username` | `cassandra` | Cassandra username |
| `axon_server_password` | `cassandra` | Cassandra password |
| `axon_server_local_dc` | `{{ cassandra_dc \| default('axonops') }}` | Local datacenter name |
| `axon_server_cql_keyspace_replication` | NetworkTopologyStrategy | Replication strategy for AxonOps keyspaces |

### TLS Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `axon_server_tls_mode` | `disabled` | TLS mode: `disabled`, `TLS`, or `mTLS` |

### LDAP Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `axon_server_ldap_enabled` | `false` | Enable LDAP authentication |
| `axon_server_ldap_setting` | - | LDAP configuration object (see example below) |

### Retention Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `axon_server_retention.events` | `4w` | Retention period for events |
| `axon_server_retention.security_events` | `8w` | Retention period for security events |
| `axon_server_retention.metrics.high_resolution` | `30d` | High-resolution metrics retention |
| `axon_server_retention.metrics.med_resolution` | `24w` | Medium-resolution metrics retention |
| `axon_server_retention.metrics.low_resolution` | `24M` | Low-resolution metrics retention |
| `axon_server_retention.metrics.super_low_resolution` | `3y` | Super low-resolution metrics retention |
| `axon_server_retention.backups.local` | `10d` | Local backup retention |
| `axon_server_retention.backups.remote` | `30d` | Remote backup retention |

### Notification Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `axon_server_notification_interval` | `3h` | Interval between repeated notifications for the same alert |

### Repository Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `axon_server_public_repository` | `present` | Enable public repository |
| `axon_server_beta_repository` | `absent` | Enable beta repository |
| `axonops_debian_repository` | `deb https://packages.axonops.com/apt axonops-apt main` | Debian repository URL |
| `axonops_redhat_repository` | `https://packages.axonops.com/yum` | RedHat repository URL |

## Dependencies

- Elasticsearch (installed via `elastic` role)
- Cassandra (optional but recommended, installed via `cassandra` role)
- Java (installed automatically by dependencies)

## Example Playbooks

### Basic Self-Hosted Server

```yaml
- name: Deploy AxonOps Server
  hosts: axon-server
  become: true
  vars:
    axon_server_cql_hosts:
      - localhost:9042
    axon_server_elastic_hosts:
      - http://127.0.0.1:9200

  roles:
    - role: axonops.axonops.server
```

### Complete Server Stack

```yaml
- name: Deploy Complete AxonOps Server Stack
  hosts: axon-server
  become: true
  vars:
    install_cassandra: true
    install_elastic: true
    java_pkg: java-17-openjdk-headless

    # Cassandra Configuration
    cassandra_cluster_name: axonops
    cassandra_dc: default
    cassandra_rack: rack1
    axon_java_agent: "axon-cassandra5.0-agent-jdk17"
    axon_agent_server_host: localhost
    axon_agent_tls_mode: "disabled"
    axon_agent_customer_name: "mycompany"
    cassandra_start_on_boot: true
    cassandra_listen_address: "localhost"
    cassandra_rpc_address: "localhost"

    # Elasticsearch Configuration
    es_version: 7.17.0
    es_heap_size: 2g

    # AxonOps Server Configuration
    axon_server_cql_hosts:
      - localhost:9042
    axon_server_elastic_hosts:
      - http://127.0.0.1:9200
    axon_server_listen_address: 0.0.0.0

    # Dashboard Configuration
    axon_dash_listen_address: 0.0.0.0

  roles:
    - role: axonops.axonops.java
      tags: java

    - role: axonops.axonops.agent
      tags: agent

    - role: axonops.axonops.cassandra
      tags: cassandra
      when: install_cassandra

    - role: axonops.axonops.elastic
      tags: elastic
      when: install_elastic

    - role: axonops.axonops.server
      tags: server

    - role: axonops.axonops.dash
      tags: dash
```

### Server with External Cassandra

```yaml
- name: Deploy AxonOps Server with External Cassandra
  hosts: axon-server
  become: true
  vars:
    axon_server_cql_hosts:
      - cassandra-1.example.com:9042
      - cassandra-2.example.com:9042
      - cassandra-3.example.com:9042
    axon_server_username: axonops_user
    axon_server_password: "{{ vault_cassandra_password }}"
    axon_server_local_dc: DC1
    axon_server_elastic_hosts:
      - http://127.0.0.1:9200

  roles:
    - role: axonops.axonops.elastic
      tags: elastic

    - role: axonops.axonops.server
      tags: server
```

### Server with LDAP Authentication

```yaml
- name: Deploy AxonOps Server with LDAP
  hosts: axon-server
  become: true
  vars:
    axon_server_cql_hosts:
      - localhost:9042
    axon_server_elastic_hosts:
      - http://127.0.0.1:9200
    axon_server_ldap_enabled: true
    axon_server_ldap_setting:
      serverName: "production_ldap"
      base: "dc=example,dc=com"
      host: "ldap.example.com"
      port: 636
      useSSL: true
      bindDN: "cn=admin,dc=example,dc=com"
      bindPassword: "{{ vault_ldap_password }}"
      userFilter: "(uid=%s)"
      rolesAttribute: memberOf
      callAttempts: 3
      rolesMapping:
        _global_:
          superUserRole: 'cn=axonops_super,ou=Groups,dc=example,dc=com'
          adminRole: 'cn=axonops_admin,ou=Groups,dc=example,dc=com'
          readOnlyRole: 'cn=axonops_readonly,ou=Groups,dc=example,dc=com'
          backupAdminRole: 'cn=axonops_backup,ou=Groups,dc=example,dc=com'
          dbaRole: 'cn=axonops_dba,ou=Groups,dc=example,dc=com'

  roles:
    - role: axonops.axonops.server
```

### Server with Custom Retention

```yaml
- name: Deploy AxonOps Server with Custom Retention
  hosts: axon-server
  become: true
  vars:
    axon_server_cql_hosts:
      - localhost:9042
    axon_server_elastic_hosts:
      - http://127.0.0.1:9200
    axon_server_retention:
      events: 8w
      security_events: 12w
      metrics:
        high_resolution: 60d
        med_resolution: 48w
        low_resolution: 36M
        super_low_resolution: 5y
      backups:
        local: 7d
        remote: 90d

  roles:
    - role: axonops.axonops.server
```

### Server with Elasticsearch Authentication

```yaml
- name: Deploy AxonOps Server with Elasticsearch Security
  hosts: axon-server
  become: true
  vars:
    axon_server_cql_hosts:
      - localhost:9042
    axon_server_elastic_hosts:
      - https://127.0.0.1:9200
    axon_server_elastic_username: elastic
    axon_server_elastic_password: "{{ vault_elastic_password }}"
    axon_server_elastic_tls_skip_verify: false

  roles:
    - role: axonops.axonops.server
```

### Multi-Organization Configuration

```yaml
- name: Deploy AxonOps Server for Multiple Organizations
  hosts: axon-server
  become: true
  vars:
    axon_server_cql_hosts:
      - localhost:9042
    axon_server_elastic_hosts:
      - http://127.0.0.1:9200
    axon_server_org_name: "production"

  roles:
    - role: axonops.axonops.server
```

## Post-Installation

After installation, the AxonOps Server will be running on the configured listen address and port (default: `http://0.0.0.0:8080`).

### Initial Setup

1. Access the AxonOps Dashboard (typically on port 3000)
2. Log in with the default credentials (set during installation)
3. Configure your first organization and cluster
4. Install the AxonOps Agent on your Cassandra nodes

### Verify Installation

```bash
# Check server status
systemctl status axon-server

# Check server logs
journalctl -u axon-server -f

# Verify API is responding
curl http://localhost:8080/health
```

## Cassandra Keyspace Replication

The server creates several keyspaces in Cassandra. Configure replication appropriately:

```yaml
axon_server_cql_keyspace_replication: "{ 'class': 'NetworkTopologyStrategy', 'DC1': 3 }"
```

For single datacenter:
```yaml
axon_server_cql_keyspace_replication: "{ 'class': 'NetworkTopologyStrategy', 'DC1': 1 }"
```

For multiple datacenters:
```yaml
axon_server_cql_keyspace_replication: "{ 'class': 'NetworkTopologyStrategy', 'DC1': 3, 'DC2': 3 }"
```

## Version Compatibility

### Elasticsearch Configuration Format

The role automatically detects the server version and applies the appropriate Elasticsearch configuration format:

- **Version >= 2.0.4**: Uses new `hosts` array format
- **Version < 2.0.4**: Uses legacy `elastic_host` and `elastic_port` format

## Tags

- `server`: Apply all server installation and configuration tasks
- `axonops-server`: Alias for server tag

## Notes

- **SaaS vs Self-Hosted**: Only use this role for self-hosted deployments. For SaaS, use `agents.axonops.cloud` as your `axon_agent_server_host`
- **Resources**: Ensure adequate resources (minimum 4GB RAM recommended for production)
- **Backup**: Regularly backup the Cassandra cluster storing AxonOps data
- **Monitoring**: Monitor the AxonOps Server itself for health and performance
- **Security**: Configure TLS and authentication for production deployments
- **High Availability**: For HA deployments, consider running multiple AxonOps Server instances behind a load balancer

## Firewall Configuration

Ensure the following ports are accessible:
- `8080` (or custom): AxonOps Server API
- `1888`: Agent communication (default for self-hosted)
- `9042`: Cassandra CQL (if using local Cassandra)
- `9200`: Elasticsearch HTTP API

## License

See the main collection LICENSE file.

## Author

AxonOps Limited
