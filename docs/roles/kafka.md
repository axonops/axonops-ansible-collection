# Kafka Role

Installs and configures Apache Kafka in **KRaft mode** (no ZooKeeper) on RHEL/Debian-family systems. The role handles binary installation, cluster UUID management, storage formatting, systemd service configuration, and optional topic creation.

## Overview

| Item | Value |
|------|-------|
| Default version | 4.4.0 |
| Mode | KRaft only (no ZooKeeper) |
| Installation | Tar archive from Apache mirrors |
| Topologies | Combined broker+controller, broker-only, controller-only |
| TLS/SASL/ACL | Opt-in via `kafka_security_enabled`; PLAINTEXT remains the default |

## Requirements

- Ansible 2.12+
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

The full variable reference, with types, defaults and allowed values, is generated from `meta/argument_specs.yml` and lives in the [role README](../../roles/kafka/README.md#variable-reference). Run `ansible-doc -t role axonops.axonops.kafka` for the same information on the command line.

## Tags

| Tag | What it runs |
|-----|-------------|
| `install` | Download, extract, user/group, symlink, service unit |
| `firewall` | Open broker/controller ports in firewalld or ufw |
| `security` | Master tag for TLS, SASL and ACL configuration |
| `tls` | Subset of `security` covering certificate handling |
| `sasl` | Subset of `security` covering SASL pre-flight and SCRAM user management |
| `acl` | Apply declarative `kafka_acls` rules via `kafka-acls.sh` |
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
- **Security** — TLS, SASL (SCRAM-SHA-512 / PLAIN) and ACL are opt-in via `kafka_security_enabled`. With the master switch off the role's behaviour is unchanged from previous versions. See the Security sections above for details.
- **AxonOps agent** — the role adds the `axonops` user to the `kafka` group and the `kafka` user to the `axonops` group so that `axon-agent` can access Kafka files without requiring root.

## License

Apache 2.0 — see [LICENSE](../../LICENSE) for details.

## Author

[AxonOps Limited](https://axonops.com)
