# Cassandra Role

## Overview

The `cassandra` role installs and configures Apache Cassandra on target nodes. It supports multiple Cassandra versions including 3.11, 4.x, and 5.x, with extensive configuration options for production deployments.

## Requirements

- Ansible 2.9 or higher
- Target system running a supported Linux distribution (RHEL, CentOS, Ubuntu, Debian)
- Sufficient system resources (memory, disk space) for Cassandra
- Java installed (use the `java` role or ensure Java is available)

## Important Note for Cassandra 5.0

Apache Cassandra 5.0 introduced significant configuration changes, particularly the shift from parameter names that include units to explicit unit declarations in values. For example:

```yaml
# Cassandra 4.1
dynamic_snitch_reset_interval_in_ms: 600000

# Cassandra 5.0
dynamic_snitch_reset_interval: 600000ms
```

Before running this playbook for Cassandra 5.0, review the variables in [roles/cassandra/defaults/main.yml](../../roles/cassandra/defaults/main.yml) and compare them against the appropriate template.

## Role Variables

### Basic Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `cassandra_version` | `5.0.5` | Version of Cassandra to install |
| `cassandra_cluster_name` | `default` | Name of the Cassandra cluster |
| `cassandra_dc` | `default` | Datacenter name |
| `cassandra_rack` | `rack1` | Rack name |
| `cassandra_install_format` | `pkg` | Installation format: `pkg` or `tar` |
| `cassandra_start_on_boot` | `false` | Enable Cassandra to start on boot |

### Memory Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `cassandra_max_heap_size` | `1G` | Maximum heap size for JVM |

### Network Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `cassandra_listen_address` | `{{ ansible_default_ipv4.address }}` | IP address Cassandra listens on |
| `cassandra_rpc_address` | `{{ ansible_default_ipv4.address }}` | RPC address for client connections |
| `cassandra_seeds` | `127.0.0.1` | Comma-separated list of seed nodes |
| `cassandra_storage_port` | `7000` | Port for inter-node communication |
| `cassandra_ssl_storage_port` | `7001` | SSL port for inter-node communication |
| `cassandra_native_transport_port` | `9042` | Port for CQL client connections |
| `cassandra_jmx_port` | `7199` | JMX port |

### Data Directory Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `cassandra_data_directory` | `/var/lib/cassandra` | Base data directory |
| `cassandra_commitlog_directory` | `/var/lib/cassandra/commitlog` | Commit log directory |
| `cassandra_saved_caches_directory` | `/var/lib/cassandra/saved_caches` | Saved caches directory |
| `cassandra_hints_directory` | `/var/lib/cassandra/hints` | Hints directory |
| `cassandra_log_dir` | `/var/log/cassandra` | Log directory |

### Authentication and Authorization

| Variable | Default | Description |
|----------|---------|-------------|
| `cassandra_authenticator` | `PasswordAuthenticator` | Authentication class |
| `cassandra_authorizer` | `CassandraAuthorizer` | Authorization class |
| `cassandra_role_manager` | `CassandraRoleManager` | Role manager class |

### Performance Tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `cassandra_num_tokens` | `16` | Number of virtual nodes |
| `cassandra_concurrent_reads` | `32` | Concurrent read operations |
| `cassandra_concurrent_writes` | `32` | Concurrent write operations |
| `cassandra_concurrent_compactors` | `1` | Number of concurrent compactors |
| `cassandra_compaction_throughput` | `64MiB/s` | Compaction throughput limit |
| `cassandra_stream_throughput_outbound` | `24MiB/s` | Stream throughput limit |

### SSL/TLS Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `cassandra_ssl_internode_encryption` | `none` | Internode encryption: `none`, `all`, `dc`, or `rack` |
| `cassandra_ssl_client_encryption_enabled` | `false` | Enable client-to-node encryption |
| `cassandra_ssl_internode_keystore_file` | `conf/.keystore` | Keystore file path |
| `cassandra_ssl_internode_keystore_pass` | `cassandra` | Keystore password |
| `cassandra_ssl_truststore_file` | `conf/.truststore` | Truststore file path |
| `cassandra_ssl_truststore_pass` | `cassandra` | Truststore password |

## Dependencies

- Java (JDK 11 for Cassandra 4.x, JDK 17 for Cassandra 5.x)

## Example Playbooks

### Basic Single Node Installation

```yaml
- name: Install Cassandra 5.0
  hosts: cassandra
  become: true
  vars:
    cassandra_version: 5.0.5
    cassandra_cluster_name: test-cluster
    cassandra_dc: DC1

  roles:
    - role: axonops.axonops.java
      vars:
        java_pkg: java-17-openjdk-headless

    - role: axonops.axonops.cassandra
```

### Multi-Node Cluster

```yaml
- name: Deploy Cassandra Cluster
  hosts: cassandra
  become: true
  vars:
    cassandra_version: 4.1.3
    cassandra_cluster_name: production
    cassandra_dc: DC1
    cassandra_rack: rack1
    cassandra_seeds: "{{ groups['cassandra'] | map('extract', hostvars, ['ansible_default_ipv4', 'address']) | list | join(',') }}"
    cassandra_listen_address: "{{ ansible_default_ipv4.address }}"
    cassandra_rpc_address: "{{ ansible_default_ipv4.address }}"
    cassandra_max_heap_size: 8G

  roles:
    - role: axonops.axonops.java
      vars:
        java_pkg: java-11-openjdk-headless

    - role: axonops.axonops.cassandra
```

### Cassandra with SSL/TLS

```yaml
- name: Deploy Cassandra with SSL
  hosts: cassandra
  become: true
  vars:
    cassandra_cluster_name: secure-cluster
    cassandra_dc: DC1
    cassandra_ssl_internode_encryption: all
    cassandra_ssl_client_encryption_enabled: true
    cassandra_ssl_internode_keystore_file: /etc/cassandra/conf/.keystore
    cassandra_ssl_internode_keystore_pass: "{{ vault_keystore_password }}"
    cassandra_ssl_truststore_file: /etc/cassandra/conf/.truststore
    cassandra_ssl_truststore_pass: "{{ vault_truststore_password }}"

  roles:
    - role: axonops.axonops.cassandra
```

### Production Configuration Example

```yaml
- name: Deploy Production Cassandra Cluster
  hosts: cassandra
  become: true
  vars:
    # Cluster Configuration
    cassandra_version: 5.0.5
    cassandra_cluster_name: production
    cassandra_dc: DC1
    cassandra_rack: "{{ ansible_hostname | regex_replace('^.*rack([0-9]+).*$', 'rack\\1') }}"

    # Network
    cassandra_seeds: "192.168.1.10,192.168.1.11,192.168.1.12"
    cassandra_listen_address: "{{ ansible_default_ipv4.address }}"
    cassandra_rpc_address: "{{ ansible_default_ipv4.address }}"

    # Memory
    cassandra_max_heap_size: 16G

    # Performance
    cassandra_concurrent_reads: 64
    cassandra_concurrent_writes: 64
    cassandra_concurrent_compactors: 4
    cassandra_compaction_throughput: 128MiB/s

    # Data Directories
    cassandra_data_directory: /data/cassandra
    cassandra_commitlog_directory: /commitlog/cassandra

    # Authentication
    cassandra_authenticator: PasswordAuthenticator
    cassandra_authorizer: CassandraAuthorizer

    # Backup
    cassandra_incremental_backups: true
    cassandra_auto_snapshot: true

  roles:
    - role: axonops.axonops.java
      vars:
        java_pkg: java-17-openjdk-headless

    - role: axonops.axonops.cassandra
```

### Cassandra 4.1 Example

```yaml
- name: Deploy Cassandra 4.1
  hosts: cassandra
  become: true
  vars:
    cassandra_version: 4.1.3
    cassandra_cluster_name: cassandra-4
    cassandra_dc: DC1
    cassandra_seeds: "{{ groups['cassandra'][0] }}"

  roles:
    - role: axonops.axonops.java
      vars:
        java_pkg: java-11-openjdk-headless

    - role: axonops.axonops.cassandra
```

## Advanced Configuration

### Transparent Data Encryption

```yaml
cassandra_transparent_data_encryption_options:
  enabled: true
  chunk_length_kb: 64
  cipher: "AES/CBC/PKCS5Padding"
  key_alias: "cassandra:1"
  key_provider:
    - class_name: "org.apache.cassandra.security.JKSKeyProvider"
      parameters:
        - keystore: "/etc/cassandra/conf/.keystore"
          keystore_password: "{{ vault_keystore_password }}"
          store_type: "JCEKS"
          key_password: "{{ vault_key_password }}"
```

### JMX Authentication

```yaml
cassandra_jmx_user: "cassandra"
cassandra_jmx_password: "{{ vault_jmx_password }}"
cassandra_jmx_password_file: "/opt/cassandra/conf/jmxremote.password"
cassandra_jmx_access_file: "/opt/cassandra/conf/jmxremote.access"
```

## Tags

- `cassandra`: Apply all Cassandra installation and configuration tasks

## Notes

- **Heap Size**: Adjust `cassandra_max_heap_size` based on your available memory. A common guideline is 8-14GB for production systems
- **Seeds**: List 2-3 nodes per datacenter as seeds. More seeds are not necessarily better
- **Data Directories**: For production, use separate disks for data and commit logs
- **Start on Boot**: It's recommended to leave `cassandra_start_on_boot` as `false` to prevent automatic startup during maintenance
- **Version Compatibility**: Ensure template compatibility when upgrading between major versions

## License

See the main collection LICENSE file.

## Author

AxonOps Limited
