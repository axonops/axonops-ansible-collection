# Kafka Role

Installs and configures Apache Kafka in **KRaft mode** (no ZooKeeper) on RHEL/Debian-family systems. The role handles binary installation, cluster UUID management, storage formatting, systemd service configuration, and optional topic creation.

## Overview

| Item | Value |
|------|-------|
| Default version | 4.0.0 |
| Mode | KRaft only (no ZooKeeper) |
| Installation | Tar archive from Apache mirrors |
| Topologies | Combined broker+controller, broker-only, controller-only |
| TLS/SASL | Not included — planned for a future release |

## Requirements

- Ansible 2.10+
- Java 17 on target hosts (installed by the role via `kafka_java_version` unless `kafka_java_install: false`)
- All Kafka hosts must be in the **same play** — the role builds the controller quorum voters list from `ansible_play_hosts`

## How It Works

1. Creates the `kafka` system user and group
2. Downloads and extracts the Kafka tarball with checksum verification (SHA-512 fetched from `downloads.apache.org`; tarball fetched from `archive.apache.org`)
3. Creates a symlink at `/opt/kafka` pointing to `/opt/kafka_2.13-<version>`
4. Writes `/etc/sysconfig/kafka` with JVM heap and opts settings
5. Templates `server.properties` for KRaft mode based on `kafka_node_roles`
6. On first run: generates a cluster UUID, persists it to `/opt/kafka/CLUSTER_UUID.lock`, and formats storage directories
7. On subsequent runs: reads the UUID from the lock file — UUID is never regenerated
8. Enables and optionally starts the `kafka` systemd service
9. Creates any topics defined in `kafka_topics` (idempotent — requires a running broker)

## Role Variables

### Version and Installation

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_version` | `"4.0.0"` | Kafka version to install |
| `kafka_scala_version` | `"2.13"` | Scala version for tarball selection |
| `kafka_java_version` | `17` | OpenJDK version to install |
| `kafka_java_install` | `true` | Set to `false` to skip Java installation if it is already managed separately |
| `kafka_install_root` | `/opt` | Base directory for Kafka installation |
| `kafka_user` | `kafka` | System user that runs Kafka |
| `kafka_group` | `kafka` | System group for Kafka |

### Paths

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_log_dir` | `/var/log/kafka` | JVM/service stdout log directory |
| `kafka_data_dirs` | `[/var/lib/kafka]` | Kafka topic/partition data directories |

### KRaft Cluster

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_node_id` | **required** | Unique integer ID for this node. Must be set per host in inventory. |
| `kafka_node_roles` | `[broker, controller]` | Roles for this node. Valid values: `broker`, `controller`, or both. |
| `kafka_node_ip` | `ansible_default_ipv4.address` | IP this node advertises. Override when the default interface is wrong. |
| `kafka_cluster_id` | auto-generated | Cluster UUID. Auto-generated on first run and persisted to `/opt/kafka/CLUSTER_UUID.lock`. Set explicitly to pin a known UUID. |

### Listeners

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_listeners` | `[]` | Override auto-derived listeners. Leave empty to use role defaults based on `kafka_node_roles`. |
| `kafka_inter_broker_listener_name` | `PLAINTEXT` | Listener name used for inter-broker communication. |

Auto-derived listener defaults by topology:

| Node roles | Listeners |
|-----------|-----------|
| `[broker, controller]` | `PLAINTEXT://:9092,CONTROLLER://:9093` |
| `[broker]` | `PLAINTEXT://:9092` |
| `[controller]` | `CONTROLLER://:9093` |

### Performance

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_heap_size` | `1G` | JVM heap size (sets both Xmx and Xms) |
| `kafka_opts` | `[]` | Additional JVM flags (list or string) |
| `kafka_num_network_threads` | `3` | Network handler threads |
| `kafka_num_io_threads` | `8` | I/O handler threads |
| `kafka_socket_send_buffer_bytes` | `102400` | Socket send buffer |
| `kafka_socket_receive_buffer_bytes` | `102400` | Socket receive buffer |
| `kafka_socket_request_max_bytes` | `104857600` | Maximum request size |

### Topics and Replication

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_num_partitions` | `1` | Default number of partitions for new topics |
| `kafka_replication_factor` | `1` | Default replication factor |
| `kafka_offsets_topic_replication_factor` | `1` | `__consumer_offsets` replication factor |
| `kafka_transaction_state_log_replication_factor` | `1` | `__transaction_state` replication factor |
| `kafka_transaction_state_log_min_isr` | `1` | Minimum in-sync replicas for `__transaction_state` |

### Log Retention

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_log_retention_hours` | `168` | Retain log segments for this many hours (7 days) |
| `kafka_log_retention_bytes` | `-1` | Byte-based retention limit. `-1` disables it. |
| `kafka_log_segment_bytes` | `1073741824` | Maximum log segment size (1 GiB) |
| `kafka_log_retention_check_interval_ms` | `300000` | How often to check log retention (5 minutes) |

### Service Control

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_start_on_install` | `false` | Start Kafka at the end of the play |
| `kafka_start_on_boot` | `false` | Enable Kafka service at boot |
| `kafka_configure_firewall` | `true` | Open broker/controller ports in firewalld or ufw if either is active. Set to `false` to skip. |

> **Note**: It is recommended to leave both `false` on new multi-node clusters. Start brokers manually after validating all nodes are configured correctly.

### Topics

| Variable | Default | Description                                                                                                          |
|----------|---------|----------------------------------------------------------------------------------------------------------------------|
| `kafka_topics` | `[]` | List of topics to create idempotently. Requires `kafka_start_on_install: true` or a running broker on the target hosts. |

Topic entry fields:

| Field | Required | Description |
|-------|----------|-------------|
| `name` | yes | Topic name |
| `partitions` | no | Number of partitions (defaults to `kafka_num_partitions`) |
| `replication_factor` | no | Replication factor (defaults to `kafka_replication_factor`) |
| `config` | no | Dict of topic config keys (underscores converted to dots automatically) |

### Miscellaneous

| Variable                  | Default      | Description                                                                                        |
|---------------------------|--------------|----------------------------------------------------------------------------------------------------|
| `kafka_additional_config` | `{}`         | Extra key/value pairs appended verbatim to `server.properties`                                     |
| `kafka_checksum`          | auto-fetched | Override the tarball SHA-512 checksum. Only needed if the Apache checksum endpoint is unreachable. |

### Security (TLS)

Security is opt-in via `kafka_security_enabled`. When `false` (default), behaviour is unchanged and listeners stay PLAINTEXT.

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_security_enabled` | `false` | Master switch; nothing in `security.yml` runs unless `true` |
| `kafka_tls_enabled` | `false` | Encrypt broker and controller listeners with TLS |
| `kafka_tls_mode` | `custom` | `custom` \| `pki_agent` \| `generate` |
| `kafka_tls_client_auth` | `required` | `required` (mTLS) \| `requested` \| `none` |
| `kafka_tls_cert` / `kafka_tls_key` / `kafka_tls_ca` | `""` | Control-node PEM paths (custom mode) |
| `kafka_tls_key_password` | `""` | Password for an encrypted private key (optional) |
| `kafka_tls_pki_cert_path` / `kafka_tls_pki_key_path` / `kafka_tls_pki_ca_path` | `/opt/tls/kafka/{cert,key,ca}.pem` | Broker-host paths written by `axonops.axonops.pki_agent` |
| `kafka_tls_generate_ca_cn` | `Kafka Dev CA` | CN of the self-signed CA in `generate` mode |
| `kafka_tls_generate_validity_days` | `3650` | Validity of generated CA + per-host certs |
| `kafka_tls_remote_dir` | `/etc/kafka/tls` | On-disk location of `keystore.pem` and `ca.pem` |

The role assembles `keystore.pem` (cert chain + key concatenated) and `ca.pem` in `kafka_tls_remote_dir` regardless of source mode. Kafka loads them via `ssl.keystore.type=PEM`.

**`custom` mode** — supply paths to PEM files on the control node:

```yaml
kafka_security_enabled: true
kafka_tls_enabled: true
kafka_tls_mode: custom
kafka_tls_cert: /home/ops/secrets/kafka.crt
kafka_tls_key: /home/ops/secrets/kafka.key
kafka_tls_ca: /home/ops/secrets/ca.crt
```

**`pki_agent` mode** — pair with `axonops.axonops.pki_agent`. Set the agent's `reload_command` to the helper script the role installs at `/usr/local/sbin/kafka-reload-tls.sh`; it reassembles the keystore on rotation and restarts Kafka:

```yaml
- role: axonops.axonops.pki_agent
  vars:
    pki_agent_certificates:
      - name: kafka
        pki_mount: pki
        pki_role: kafka
        common_name: "{{ inventory_hostname }}"
        cert_path: /opt/tls/kafka/cert.pem
        key_path: /opt/tls/kafka/key.pem
        ca_path: /opt/tls/kafka/ca.pem
        reload_command: /usr/local/sbin/kafka-reload-tls.sh

- role: axonops.axonops.kafka
  vars:
    kafka_security_enabled: true
    kafka_tls_enabled: true
    kafka_tls_mode: pki_agent
```

**`generate` mode (DEV ONLY)** — role creates a self-signed CA on the control node and signs per-host certs. Requires `community.crypto` and the Python `cryptography` package on the control node. **Do not use in production.**

```yaml
kafka_security_enabled: true
kafka_tls_enabled: true
kafka_tls_mode: generate
```

### AxonOps Agent Integration

| Variable | Default | Description |
|----------|---------|-------------|
| `kafka_axonops_agent_enabled` | `false` | Set to `true` to install and configure the AxonOps agent on Kafka nodes |
| `kafka_axonops_org` | — | **Required when enabled.** Your AxonOps organisation name |
| `kafka_axonops_key` | — | SaaS API key (required for `axonops.cloud`) |
| `kafka_axonops_server_host` | `agents.axonops.cloud` | AxonOps server host |
| `kafka_axonops_java_agent` | `axon-kafka4-agent` | Kafka Java agent package name |
| `kafka_axonops_agent_version` | latest | Pin the `axon-agent` package version |
| `kafka_axonops_java_agent_version` | latest | Pin the Java agent JAR version |
| `kafka_axonops_cluster_name` | — | Override the cluster name shown in AxonOps |

When enabled, the role invokes `axonops.axonops.agent` with the Kafka-specific package and injects the agent JVM options into `kafka-server-start.sh` before the `exec` line.

## Tags

| Tag | What it runs |
|-----|-------------|
| `install` | Download, extract, user/group, symlink, service unit |
| `firewall` | Open broker/controller ports in firewalld or ufw |
| `security` | TLS material distribution (stage 1 only — SASL/ACL pending) |
| `tls` | Subset of `security` covering certificate handling |
| `config` | `server.properties` and `/etc/sysconfig/kafka` |
| `cluster` | UUID management and storage formatting |
| `topics` | Topic creation |
| `service` | Start/enable systemd service |
| `axonops_user` | Create `axonops` user and cross-group membership |
| `axonops_agent` | Install and configure AxonOps agent |

## Example Playbooks

### Single-node (development)

```yaml
- hosts: kafka
  roles:
    - role: axonops.axonops.kafka
  vars:
    kafka_node_id: 1
    kafka_start_on_install: true
    kafka_start_on_boot: true
```

### Three-node cluster (combined broker + controller)

Set per-host variables in inventory:

```ini
[kafka]
kafka1 ansible_host=192.168.1.11 kafka_node_id=1 kafka_node_ip=192.168.1.11
kafka2 ansible_host=192.168.1.12 kafka_node_id=2 kafka_node_ip=192.168.1.12
kafka3 ansible_host=192.168.1.13 kafka_node_id=3 kafka_node_ip=192.168.1.13
```

```yaml
- hosts: kafka
  roles:
    - role: axonops.axonops.kafka
  vars:
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
      - name: my-events
        partitions: 9
        replication_factor: 3
```

### Separated broker and controller nodes

> **Important**: All nodes — both controllers and brokers — must be targeted by a **single play**. The role uses `ansible_play_hosts` to build the controller quorum voters list. If controllers and brokers run in separate plays, brokers will not know about the controllers and the cluster will not form.

Inventory:

```ini
[kafka_controllers]
ctrl1 ansible_host=10.0.0.1 kafka_node_id=1 kafka_node_ip=10.0.0.1
ctrl2 ansible_host=10.0.0.2 kafka_node_id=2 kafka_node_ip=10.0.0.2
ctrl3 ansible_host=10.0.0.3 kafka_node_id=3 kafka_node_ip=10.0.0.3

[kafka_brokers]
broker1 ansible_host=10.0.1.1 kafka_node_id=4 kafka_node_ip=10.0.1.1
broker2 ansible_host=10.0.1.2 kafka_node_id=5 kafka_node_ip=10.0.1.2
broker3 ansible_host=10.0.1.3 kafka_node_id=6 kafka_node_ip=10.0.1.3

[kafka:children]
kafka_controllers
kafka_brokers
```

`group_vars/kafka_controllers/main.yml`:

```yaml
kafka_node_roles:
  - controller
```

`group_vars/kafka_brokers/main.yml`:

```yaml
kafka_node_roles:
  - broker
```

Playbook — targets the parent `kafka` group so that all nodes are in the same play:

```yaml
- hosts: kafka
  roles:
    - role: axonops.axonops.kafka
  vars:
    kafka_heap_size: 4G
    kafka_replication_factor: 3
    kafka_offsets_topic_replication_factor: 3
    kafka_transaction_state_log_replication_factor: 3
    kafka_transaction_state_log_min_isr: 2
    kafka_start_on_install: true
    kafka_start_on_boot: true
```

### Custom topics with retention

```yaml
kafka_topics:
  - name: events
    partitions: 12
    replication_factor: 3
    config:
      retention_ms: 604800000    # 7 days
      cleanup_policy: delete
  - name: audit-log
    partitions: 3
    replication_factor: 3
    config:
      retention_ms: 2592000000   # 30 days
      retention_bytes: 10737418240
```

## Notes

- **`kafka_node_id` is mandatory** — the role fails immediately if it is not defined for a host.
- **UUID persistence** — the cluster UUID is written to `/opt/kafka/CLUSTER_UUID.lock` on the first controller node and is never regenerated. Delete this file only if you are intentionally re-initialising the cluster.
- **Storage format** — `kafka-storage.sh format` is skipped if `meta.properties` already exists in any data directory. Re-runs are safe.
- **Java 17** — Kafka 4.x requires Java 17. The role installs `openjdk-17-jre-headless` (Debian) or `java-17-openjdk-headless` (RHEL). Set `kafka_java_install: false` to skip this step if Java is managed by another role.
- **Topics require a running broker** — `kafka_topics` is processed only when `kafka_start_on_install: true` and the broker port is reachable. Topics are not created on configuration-only runs.
- **TLS/SASL** — not supported in this release. Planned for a future version.
- **AxonOps agent** — the role adds the `axonops` user to the `kafka` group and the `kafka` user to the `axonops` group so that `axon-agent` can access Kafka files without requiring root.

## License

Apache 2.0 — see [LICENSE](../../LICENSE) for details.

## Author

[AxonOps Limited](https://axonops.com)
