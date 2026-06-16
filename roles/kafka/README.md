# AxonOps Kafka Ansible Role

<p align="center">
  <a href="https://axonops.com">
    <img src="https://digitalis-marketplace-assets.s3.us-east-1.amazonaws.com/AxonopsDigitalMaster_AxonopsFullLogoBlue.jpg" alt="AxonOps" width="300">
  </a>
</p>

<p align="center">
  <em>Built and maintained by <a href="https://axonops.com">AxonOps</a></em>
</p>

Installs and configures Apache Kafka in KRaft mode (no ZooKeeper required) on RHEL, Debian, and Ubuntu hosts.

## Requirements

- **Ansible** 2.10 or higher
- **OS**: RHEL / Rocky / AlmaLinux 8, 9, or 10; Fedora; Debian; Ubuntu
- **Java 17**: required for Kafka 4.x. The role installs Java automatically via `axonops.axonops.java` when `kafka_java_install: true` (the default). Set `kafka_java_install: false` if you manage Java separately.
- **Collections**: `ansible.posix`, `community.general` (install via `ansible-galaxy collection install -r requirements.yml`)
- **`become: true`** is required — the role installs packages, creates system users, and manages systemd units.

## KRaft-only mode

This role uses **KRaft** exclusively. ZooKeeper is not supported and no ZooKeeper ensemble is needed. Every Kafka node in the play must have a unique `kafka_node_id` set in inventory.

## Quick Start

```yaml
# site.yml — single-node Kafka on one host
- hosts: kafka
  become: true
  roles:
    - role: axonops.axonops.kafka
      vars:
        kafka_node_id: 1        # mandatory — must be unique per host
        kafka_start_on_install: true
        kafka_start_on_boot: true
```

```ini
# inventory/hosts
[kafka]
kafka1.example.com kafka_node_id=1
```

## Usage Examples

### Single-node development broker

A minimal setup — combined broker/controller on a single host, started immediately:

```yaml
- hosts: kafka
  become: true
  roles:
    - role: axonops.axonops.kafka
      vars:
        kafka_node_id: 1
        kafka_heap_size: 512M
        kafka_start_on_install: true
        kafka_start_on_boot: true
        kafka_topics:
          - name: events
            partitions: 1
            replication_factor: 1
```

### Three-node production KRaft cluster

Each broker runs both broker and controller roles (combined mode). Per-host `kafka_node_id` values are set in inventory:

```ini
# inventory/hosts
[kafka]
kafka1.example.com kafka_node_id=1
kafka2.example.com kafka_node_id=2
kafka3.example.com kafka_node_id=3
```

```yaml
- hosts: kafka
  become: true
  vars:
    kafka_version: "4.0.0"
    kafka_heap_size: 4G
    kafka_replication_factor: 3
    kafka_offsets_topic_replication_factor: 3
    kafka_transaction_state_log_replication_factor: 3
    kafka_transaction_state_log_min_isr: 2
    kafka_data_dirs:
      - /data/kafka
    kafka_start_on_install: true
    kafka_start_on_boot: true
    kafka_topics:
      - name: orders
        partitions: 6
        replication_factor: 3
        config:
          retention.ms: 604800000
  roles:
    - role: axonops.axonops.kafka
```

### With TLS, SCRAM authentication, and AxonOps agent

Full-security cluster with mTLS, SCRAM-SHA-512 authentication, topic ACLs, and the AxonOps monitoring agent enabled:

```yaml
- hosts: kafka
  become: true
  vars:
    kafka_heap_size: 4G
    kafka_replication_factor: 3
    kafka_data_dirs:
      - /data/kafka

    # Security
    kafka_security_enabled: true

    # TLS — supply cert/key/CA from control node
    kafka_tls_enabled: true
    kafka_tls_mode: custom
    kafka_tls_client_auth: required
    kafka_tls_cert: /path/on/control/node/kafka.crt
    kafka_tls_key: /path/on/control/node/kafka.key
    kafka_tls_ca: /path/on/control/node/ca.crt

    # SASL
    kafka_sasl_enabled: true
    kafka_sasl_mechanism: SCRAM-SHA-512
    kafka_sasl_inter_broker_user: kafka-admin
    kafka_sasl_inter_broker_password: "{{ vault_kafka_admin_password }}"
    kafka_sasl_users:
      - name: app1
        password: "{{ vault_app1_password }}"

    # ACLs
    kafka_acl_enabled: true
    kafka_acl_allow_everyone_if_no_acl: false
    kafka_acls:
      - principal: "User:app1"
        operation: Read
        resource_type: Topic
        resource_name: events
      - principal: "User:app1"
        operation: Write
        resource_type: Topic
        resource_name: events
      - principal: "User:app1"
        operation: Read
        resource_type: Group
        resource_name: "*"

    # AxonOps agent
    kafka_axonops_agent_enabled: true
    kafka_axonops_org: my-org
    kafka_axonops_cluster_name: prod-kafka
    kafka_axonops_key: "{{ vault_axonops_api_key }}"

    kafka_start_on_install: true
    kafka_start_on_boot: true

  roles:
    - role: axonops.axonops.kafka
```

## Service Control

| Variable | Default | Effect |
|----------|---------|--------|
| `kafka_start_on_install` | `false` | When `false`, the role installs and configures Kafka but does not start the service. Start it manually after validating the cluster. When `true`, the role starts the `kafka` service and waits for ports 9092 (broker) and 9093 (controller) to be reachable. |
| `kafka_start_on_boot` | `false` | Controls `systemctl enable` independently of `kafka_start_on_install`. Enabling at boot does not start the service during the play. |

SCRAM user creation, ACL application, and topic management all require a running broker — they are skipped automatically when `kafka_start_on_install: false`.

## Security

Security features are gated behind a single master switch:

```yaml
kafka_security_enabled: true
```

When `false` (default), all listeners use `PLAINTEXT` and neither TLS nor SASL tasks run. This preserves backward compatibility.

### TLS

Three provisioning modes:

| Mode | When to use |
|------|-------------|
| `custom` | You supply PEM cert/key/CA files from the control node. The role copies them to brokers. |
| `pki_agent` | The `axonops.axonops.pki_agent` role has already written PEM files on each broker host. Paths are read directly — nothing is copied. |
| `generate` | The role generates a self-signed CA and per-host certificates. **Development/test only. Do not use in production.** |

#### `custom` mode example

```yaml
kafka_security_enabled: true
kafka_tls_enabled: true
kafka_tls_mode: custom
kafka_tls_cert: /secrets/kafka.crt     # path on control node
kafka_tls_key: /secrets/kafka.key      # path on control node
kafka_tls_ca: /secrets/ca.crt          # path on control node
```

#### `pki_agent` mode example

Run `axonops.axonops.pki_agent` first to write the PEM files, then:

```yaml
kafka_security_enabled: true
kafka_tls_enabled: true
kafka_tls_mode: pki_agent
kafka_tls_pki_cert_path: /opt/tls/kafka/cert.pem   # default
kafka_tls_pki_key_path: /opt/tls/kafka/key.pem     # default
kafka_tls_pki_ca_path: /opt/tls/kafka/ca.pem       # default
```

### SASL

Two mechanisms are supported:

| Mechanism | Notes |
|-----------|-------|
| `SCRAM-SHA-512` | Recommended. Credentials are bootstrapped into the cluster metadata at `kafka-storage format` time and updated via `kafka-configs.sh` at each run. |
| `PLAIN` | Credentials are embedded in JAAS config in `server.properties`. Simpler but requires TLS to protect credentials in transit. |

The inter-broker/controller identity (`kafka_sasl_inter_broker_user`) is added to `super.users` automatically.

### ACLs

ACLs use `StandardAuthorizer` (KRaft-native, no ZooKeeper dependency). The `kafka_acls` list is declarative — the role applies rules via `kafka-acls.sh` after the broker starts. Requires `kafka_start_on_install: true` on first run.

## Node Roles

A Kafka node can run as broker, controller, or both (combined):

| `kafka_node_roles` | Description |
|--------------------|-------------|
| `[broker, controller]` | Combined node — default, recommended for small clusters |
| `[broker]` | Dedicated broker node |
| `[controller]` | Dedicated controller (quorum) node |

Listeners and the controller quorum voter list are derived automatically from the play hosts. At least one host per play must have `controller` in its `kafka_node_roles`.

## Variable Reference

### Version and installation

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_version` | `"4.0.0"` | Kafka version to install |
| `kafka_scala_version` | `"2.13"` | Scala version used in the download URL |
| `kafka_java_version` | `17` | Java major version passed to `axonops.axonops.java`. Kafka 4.x requires Java 17. |
| `kafka_java_install` | `true` | When `true`, the `axonops.axonops.java` role is called to install Java. Set `false` if Java is managed separately. |
| `kafka_install_root` | `/opt` | Parent directory for the Kafka installation (`/opt/kafka-<version>`) |
| `kafka_user` | `kafka` | System user that owns the Kafka process |
| `kafka_group` | `kafka` | System group for the Kafka user |

### Paths

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_log_dir` | `/var/log/kafka` | JVM and service stdout log directory (not Kafka partition data) |
| `kafka_data_dirs` | `["/var/lib/kafka"]` | List of directories for Kafka topic/partition data. Multiple paths spread data across disks. |

### JVM

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_heap_size` | `1G` | JVM heap size (`-Xms` / `-Xmx`). Set to 50–75% of available RAM. |
| `kafka_opts` | `[]` | Additional JVM flags. Accepts a list of strings or a single string. |

### KRaft cluster

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_node_id` | — | **Required. No default.** Unique integer ID for this broker. Set per host in inventory. The role fails without it. |
| `kafka_node_roles` | `[broker, controller]` | Roles this node runs. See [Node Roles](#node-roles). |
| `kafka_node_ip` | (auto) | IP this node advertises in `advertised.listeners`. Defaults to `ansible_default_ipv4.address`. Override for multi-homed hosts. |
| `kafka_cluster_id` | (auto) | KRaft cluster UUID. Auto-generated and persisted to disk on first format. Pin this to force a specific UUID. |

### Listeners

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_listeners` | `[]` | Override the auto-derived listener list. Empty means the role generates listeners based on node roles and security state. |
| `kafka_inter_broker_listener_name` | `""` | Override the inter-broker listener name. Auto-derived from security state when empty (`PLAINTEXT` or `SSL`). |

### Performance

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_num_network_threads` | `3` | Number of threads for network requests. Increase for high-throughput clusters. |
| `kafka_num_io_threads` | `8` | Number of threads for I/O operations. |
| `kafka_socket_send_buffer_bytes` | `102400` | Socket send buffer size in bytes. |
| `kafka_socket_receive_buffer_bytes` | `102400` | Socket receive buffer size in bytes. |
| `kafka_socket_request_max_bytes` | `104857600` | Maximum allowed request size in bytes (100 MiB). |

### Security master switch

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_security_enabled` | `false` | Master switch. When `false`, all listeners use `PLAINTEXT` and neither TLS nor SASL tasks run. |

### TLS

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_tls_enabled` | `false` | Enable TLS on broker and controller listeners. Requires `kafka_security_enabled: true`. |
| `kafka_tls_mode` | `custom` | Provisioning mode: `custom`, `pki_agent`, or `generate`. See [TLS](#tls). |
| `kafka_tls_client_auth` | `required` | Client authentication: `required` (mTLS), `requested`, or `none`. |
| `kafka_tls_cert` | `""` | (`custom` mode) Path to the PEM certificate on the **control node**. |
| `kafka_tls_key` | `""` | (`custom` mode) Path to the PEM private key on the **control node**. |
| `kafka_tls_ca` | `""` | (`custom` mode) Path to the PEM CA certificate on the **control node**. |
| `kafka_tls_key_password` | `""` | (`custom` mode) Password for the private key, if encrypted. Omit or leave empty for unencrypted keys. |
| `kafka_tls_pki_cert_path` | `/opt/tls/kafka/cert.pem` | (`pki_agent` mode) Path on the **broker host** where the cert PEM file was written by `pki_agent`. |
| `kafka_tls_pki_key_path` | `/opt/tls/kafka/key.pem` | (`pki_agent` mode) Path on the **broker host** where the key PEM file was written by `pki_agent`. |
| `kafka_tls_pki_ca_path` | `/opt/tls/kafka/ca.pem` | (`pki_agent` mode) Path on the **broker host** where the CA PEM file was written by `pki_agent`. |
| `kafka_tls_generate_ca_cn` | `"Kafka Dev CA"` | (`generate` mode) Common name for the generated CA certificate. |
| `kafka_tls_generate_validity_days` | `3650` | (`generate` mode) Certificate validity in days. |
| `kafka_tls_generate_local_dir` | `/tmp/kafka-tls-<cluster>` | (`generate` mode) Control-node directory used to stage the generated CA between hosts. |
| `kafka_tls_remote_dir` | `/etc/kafka/tls` | Remote directory on broker hosts where PEM files are placed (`custom` and `generate` modes). |

### SASL

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_sasl_enabled` | `false` | Enable SASL authentication. Requires `kafka_security_enabled: true`. |
| `kafka_sasl_mechanism` | `SCRAM-SHA-512` | SASL mechanism: `SCRAM-SHA-512` (recommended) or `PLAIN`. |
| `kafka_sasl_inter_broker_user` | `kafka-admin` | Username for inter-broker and broker-to-controller traffic. Added to `super.users` automatically. |
| `kafka_sasl_inter_broker_password` | `""` | Password for `kafka_sasl_inter_broker_user`. Store in Ansible Vault. |
| `kafka_sasl_users` | `[]` | Additional SCRAM users created via `kafka-configs.sh` after first start. Each entry: `{name: str, password: str}`. Ignored for `PLAIN`. |
| `kafka_sasl_plain_users` | `[]` | Static credentials for `PLAIN` mechanism embedded in JAAS config. Each entry: `{name: str, password: str}`. Must include the inter-broker user. Ignored for SCRAM. |

### ACLs

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_acl_enabled` | `false` | Enable `StandardAuthorizer`. Requires `kafka_security_enabled: true`. |
| `kafka_acl_super_users` | `[]` | Additional principals granted super-user privileges (e.g. `"User:admin"`). The inter-broker user is appended automatically — do not list it again. |
| `kafka_acl_allow_everyone_if_no_acl` | `false` | When `false` (production default), access is denied when no matching ACL exists. Set `true` only for development. |
| `kafka_acls` | `[]` | Declarative ACL rules applied via `kafka-acls.sh`. See example below. |

Each entry in `kafka_acls`:

| Field | Required | Values |
|-------|----------|--------|
| `principal` | yes | e.g. `"User:app1"` |
| `operation` | yes | `Read`, `Write`, `Create`, `Delete`, `Alter`, `Describe`, `ClusterAction`, `AlterConfigs`, `DescribeConfigs`, `IdempotentWrite`, `All` |
| `resource_type` | yes | `Topic`, `Group`, `Cluster`, `TransactionalId`, `DelegationToken` |
| `resource_name` | yes | Resource name or `"*"` |
| `permission` | no | `Allow` (default) or `Deny` |
| `host` | no | `"*"` (default) |
| `pattern_type` | no | `LITERAL` (default) or `PREFIXED` |

### Topic defaults

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_num_partitions` | `1` | Default number of partitions for auto-created topics. |
| `kafka_replication_factor` | `1` | Default replication factor. Set to `3` for production clusters. |

### Internal topic settings

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_offsets_topic_replication_factor` | `1` | Replication factor for `__consumer_offsets`. Set to `3` for production. |
| `kafka_transaction_state_log_replication_factor` | `1` | Replication factor for `__transaction_state`. Set to `3` for production. |
| `kafka_transaction_state_log_min_isr` | `1` | Minimum in-sync replicas for `__transaction_state`. Set to `2` for production. |

### Log retention

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_log_retention_hours` | `168` | Retain topic data for this many hours (7 days). |
| `kafka_log_retention_bytes` | `-1` | Maximum retained bytes per partition. `-1` disables the byte-based limit. |
| `kafka_log_segment_bytes` | `1073741824` | Maximum size of a single log segment file (1 GiB). |
| `kafka_log_retention_check_interval_ms` | `300000` | How often the log cleaner checks for segments to delete (ms). |

### Service control

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_start_on_install` | `false` | Start the Kafka service during the play. See [Service Control](#service-control). |
| `kafka_start_on_boot` | `false` | Enable the Kafka service at boot (`systemctl enable`). |
| `kafka_configure_firewall` | `true` | Open Kafka ports in `firewalld` or `ufw` if active. Opens 9092 (broker) and 9093 (controller) only for the roles this node runs. |

### Topic management

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_topics` | `[]` | List of topics to create if they do not already exist. Requires `kafka_start_on_install: true`. Each entry: `{name, partitions, replication_factor, config: {}}`. |

### Additional configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_additional_config` | `{}` | Key/value pairs appended verbatim to `server.properties`. Use for any Kafka property not exposed as a dedicated variable. |

### AxonOps agent integration

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_axonops_agent_enabled` | `false` | Install and configure the AxonOps agent on Kafka nodes. |
| `kafka_axonops_org` | — | **Required when agent enabled.** Organisation name in AxonOps. |
| `kafka_axonops_cluster_name` | — | **Required when agent enabled.** Cluster identifier shown in the AxonOps UI. The Kafka Java agent fails without it. |
| `kafka_axonops_key` | — | AxonOps SaaS API key. Required when connecting to `agents.axonops.cloud`. |
| `kafka_axonops_server_host` | `"agents.axonops.cloud"` | AxonOps server host. Override for self-hosted AxonOps server deployments. |
| `kafka_axonops_agent_server_port` | (auto) | Agent port: `443` for SaaS, `1888` for self-hosted. Auto-derived from `kafka_axonops_server_host`. |
| `kafka_axonops_java_agent` | `"axon-kafka4-agent"` | Kafka Java agent package name. |
| `kafka_axonops_agent_version` | (latest) | Pin the AxonOps agent version. Leave unset to install the latest available. |
| `kafka_axonops_java_agent_version` | (latest) | Pin the Kafka Java agent version. Leave unset for latest. |
| `kafka_axonops_sasl_user` | (inter-broker user) | SASL username the AxonOps agent uses for its Kafka admin client. Defaults to `kafka_sasl_inter_broker_user`. Override to use a dedicated lower-privileged identity. |
| `kafka_axonops_sasl_password` | (inter-broker password) | SASL password for `kafka_axonops_sasl_user`. |
| `kafka_axonops_client_properties_path` | `/etc/axonops/kafka_client.properties` | Path on the broker where the agent client properties file is written. |

### Kconduit (optional CLI client)

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_kconduit_enabled` | `false` | Install the [Kconduit](https://github.com/digitalis-io/kconduit) Kafka CLI client. |
| `kafka_kconduit_version` | `"0.0.4"` | Kconduit release version to install. |

## Upgrade Notes

### Changing `kafka_data_dirs` on a running cluster

Changing `kafka_data_dirs` on an existing cluster moves the storage paths. Kafka will not automatically migrate data. Drain each broker (`kafka-reassign-partitions.sh`) before changing its data directories.

### Moving from single-node to multi-node

The KRaft cluster UUID is generated and persisted on first `kafka-storage format`. A new node joining an existing cluster must use the same UUID. The role reads the existing UUID from the first formatted log directory if `kafka_cluster_id` is not set; pin it explicitly when expanding a cluster to avoid accidental re-formatting:

```yaml
kafka_cluster_id: "your-existing-cluster-uuid"
```

## License

Apache 2.0. See the collection `LICENSE` file.

## Author

AxonOps Limited — [axonops.com/contact](https://axonops.com/contact)
