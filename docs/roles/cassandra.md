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

#### JKS (default)

| Variable | Default | Description |
|----------|---------|-------------|
| `cassandra_ssl_internode_encryption` | `none` | Internode encryption: `none`, `all`, `dc`, or `rack` |
| `cassandra_ssl_client_encryption_enabled` | `false` | Enable client-to-node encryption |
| `cassandra_ssl_internode_keystore_file` | `conf/.keystore` | Keystore file path |
| `cassandra_ssl_internode_keystore_pass` | `cassandra` | Keystore password |
| `cassandra_ssl_truststore_file` | `conf/.truststore` | Truststore file path |
| `cassandra_ssl_truststore_pass` | `cassandra` | Truststore password |

#### PEM-based TLS (Cassandra 4.1+)

Cassandra 4.1 introduced `PEMBasedSslContextFactory`, which accepts PEM-encoded certificates and keys directly — no Java keystore required. The role supports two modes:

- **Inline mode**: PEM content is passed as variable values (stored in Ansible Vault). The role renders a `parameters:` block in `cassandra.yaml`.
- **File mode**: Leave `pem_private_key` empty and point the existing `keystore_file` / `truststore_file` variables at PEM files on the target node. No `parameters:` block is rendered.

**Key format requirement.** Cassandra's `PEMBasedSslContextFactory` requires **PKCS#8** private keys (`-----BEGIN PRIVATE KEY-----`). PKCS#1 keys (`-----BEGIN RSA PRIVATE KEY-----`) cause a `GeneralSecurityException: Invalid certificate format` at startup. Convert with:

```bash
openssl pkcs8 -topk8 -nocrypt -in server.key -out server-pkcs8.key
```

**`private_key` concatenation.** The `private_key` parameter must contain the private key **and** the certificate chain concatenated in a single value. Cassandra calls both `extractPrivateKey()` and `extractCertificates()` on the same field.

```bash
# Generate a PKCS#8 key and self-signed certificate
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out node.key
openssl req -new -x509 -key node.key -out node.crt -days 365 -subj "/CN=$(hostname -f)"

# Concatenate into a single value for private_key
cat node.key node.crt > node-combined.pem
```

Store the resulting PEM content in Ansible Vault.

**Internode (server_encryption_options) PEM variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `cassandra_ssl_internode_ssl_context_factory` | `""` | Set to `pem` to enable `PEMBasedSslContextFactory` for internode TLS |
| `cassandra_ssl_internode_pem_private_key` | `""` | Inline PEM: private key + certificate chain concatenated. Leave empty for file mode |
| `cassandra_ssl_internode_pem_private_key_password` | `""` | Password for an encrypted private key. Leave empty for unencrypted keys |
| `cassandra_ssl_internode_pem_trusted_certificates` | `""` | Inline PEM: CA certificate(s) used as the trust store |
| `cassandra_ssl_internode_pem_outbound_private_key` | `""` | Optional separate identity for outbound internode connections (mTLS) |
| `cassandra_ssl_internode_pem_outbound_private_key_password` | `""` | Password for the outbound private key |
| `cassandra_ssl_internode_pem_outbound_trusted_certificates` | `""` | CA certificate(s) for validating outbound connections |

**Client (client_encryption_options) PEM variables:**

| Variable | Default | Description |
|----------|---------|-------------|
| `cassandra_ssl_client_ssl_context_factory` | `""` | Set to `pem` to enable `PEMBasedSslContextFactory` for client TLS |
| `cassandra_ssl_client_pem_private_key` | `""` | Inline PEM: private key + certificate chain concatenated. Leave empty for file mode |
| `cassandra_ssl_client_pem_private_key_password` | `""` | Password for an encrypted private key |
| `cassandra_ssl_client_pem_trusted_certificates` | `""` | Inline PEM: CA certificate(s) used as the trust store |

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

### Cassandra with PEM-based TLS — inline mode (Cassandra 4.1+)

```yaml
- name: Deploy Cassandra with PEM-based TLS (inline)
  hosts: cassandra
  become: true
  vars:
    cassandra_version: "4.1.7"
    cassandra_ssl_internode_encryption: all
    cassandra_ssl_internode_ssl_context_factory: pem
    # private_key must contain the private key AND certificate chain concatenated.
    # Generate with:
    #   openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out node.key
    #   openssl req -new -x509 -key node.key -out node.crt -days 365 -subj "/CN={{ inventory_hostname }}"
    #   cat node.key node.crt > node-combined.pem
    # Store in Ansible Vault.
    cassandra_ssl_internode_pem_private_key: "{{ vault_cassandra_internode_pem_key }}"
    cassandra_ssl_internode_pem_trusted_certificates: "{{ vault_cassandra_internode_pem_ca }}"
    cassandra_ssl_client_encryption_enabled: true
    cassandra_ssl_client_ssl_context_factory: pem
    cassandra_ssl_client_pem_private_key: "{{ vault_cassandra_client_pem_key }}"
    cassandra_ssl_client_pem_trusted_certificates: "{{ vault_cassandra_client_pem_ca }}"

  roles:
    - role: axonops.axonops.java
      vars:
        java_pkg: java-11-openjdk-headless

    - role: axonops.axonops.cassandra
```

### Cassandra with PEM-based TLS — file mode (Cassandra 4.1+)

```yaml
- name: Deploy Cassandra with PEM-based TLS (file paths)
  hosts: cassandra
  become: true
  vars:
    cassandra_version: "4.1.7"
    cassandra_ssl_internode_encryption: all
    cassandra_ssl_internode_ssl_context_factory: pem
    # In file mode, leave pem_private_key empty and point keystore/truststore at PEM files.
    # The keystore PEM file must contain the private key + certificate chain concatenated.
    cassandra_ssl_internode_keystore_file: /etc/cassandra/tls/node-combined.pem
    cassandra_ssl_truststore_file: /etc/cassandra/tls/ca.pem
    cassandra_ssl_client_encryption_enabled: true
    cassandra_ssl_client_ssl_context_factory: pem
    cassandra_ssl_client_keystore_file: /etc/cassandra/tls/node-combined.pem
    cassandra_ssl_client_truststore_file: /etc/cassandra/tls/ca.pem

  roles:
    - role: axonops.axonops.java
      vars:
        java_pkg: java-11-openjdk-headless

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
