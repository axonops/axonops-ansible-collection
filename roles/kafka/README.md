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

- **Ansible** 2.12 or higher
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

#### Controller listener (KRaft)

The KRaft `CONTROLLER` listener (port 9093) always uses SASL `PLAIN`, even when `kafka_sasl_mechanism` is `SCRAM-SHA-*`. Broker and client listeners (port 9092) keep the mechanism you chose.

Why: SCRAM credentials are stored in the cluster metadata log. Controllers can only read that log after the quorum elects a leader, so controllers cannot authenticate each other's vote requests with SCRAM and a multi-controller cluster never starts.

| Listener | Protocol (TLS + SASL) | Protocol (SASL only) | Mechanism | Accepted identity |
|----------|-----------------------|----------------------|-----------|-------------------|
| Broker (`9092`) | `SASL_SSL` | `SASL_PLAINTEXT` | `kafka_sasl_mechanism` | SCRAM users or `kafka_sasl_plain_users` |
| Controller (`9093`) | `SASL_SSL` | `SASL_PLAINTEXT` | `PLAIN` | `kafka_sasl_inter_broker_user` only |

Notes:

- No extra variables. The controller listener reuses `kafka_sasl_inter_broker_user` / `kafka_sasl_inter_broker_password`.
- Enable TLS (`kafka_tls_enabled: true`) in production. Without TLS, `PLAIN` sends the inter-broker password over the network in clear text.
- For tools run with `--bootstrap-controller`, use `/opt/kafka/config/controller-admin.properties`. For tools run with `--bootstrap-server`, use `/opt/kafka/config/admin.properties`.

```bash
# Quorum status through a controller
/opt/kafka/bin/kafka-metadata-quorum.sh \
  --bootstrap-controller localhost:9093 \
  --command-config /opt/kafka/config/controller-admin.properties \
  describe --status

# Quorum status through a broker
/opt/kafka/bin/kafka-metadata-quorum.sh \
  --bootstrap-server localhost:9092 \
  --command-config /opt/kafka/config/admin.properties \
  describe --status
```

### ACLs

ACLs use `StandardAuthorizer` (KRaft-native, no ZooKeeper dependency). The `kafka_acls` list is declarative — the role applies rules via `kafka-acls.sh` after the broker starts. Existing rules are listed first and only missing rules are added, so re-runs report no change. Rules removed from `kafka_acls` are not deleted from the cluster. Requires `kafka_start_on_install: true` on first run.

## Node Roles

A Kafka node can run as broker, controller, or both (combined):

| `kafka_node_roles` | Description |
|--------------------|-------------|
| `[broker, controller]` | Combined node — default, recommended for small clusters |
| `[broker]` | Dedicated broker node |
| `[controller]` | Dedicated controller (quorum) node |

Listeners and the controller quorum voter list are derived automatically from the play hosts. At least one host per play must have `controller` in its `kafka_node_roles`.

## Variable Reference

<!-- BEGIN_ANSIBLE_DOCS -->

|Option|Description|Type|Required|Default|
|---|---|---|---|---|
| `kafka_node_id` | Unique integer ID for this node. Required, the role fails without it. Set per host in inventory. | int | yes |  |
| `kafka_version` | Kafka version to install. | str | no | 4.0.0 |
| `kafka_scala_version` | Scala version used in the download URL. | str | no | 2.13 |
| `kafka_java_version` | Java major version passed to the `axonops.axonops.java` role. Kafka 4.x requires Java 17. | int | no | 17 |
| `kafka_java_install` | When `true`, the `axonops.axonops.java` role installs Java. Set `false` if Java is managed separately. | bool | no | True |
| `kafka_install_root` | Parent directory for the Kafka installation (`/opt/kafka-<version>`). | str | no | /opt |
| `kafka_user` | System user that owns the Kafka process. | str | no | kafka |
| `kafka_group` | System group for the Kafka user. | str | no | kafka |
| `kafka_log_dir` | JVM and service stdout log directory (not Kafka partition data). | str | no | /var/log/kafka |
| `kafka_data_dirs` | Directories for Kafka topic/partition data. Multiple paths spread data across disks. | list of 'str' | no | ['/var/lib/kafka'] |
| `kafka_heap_size` | JVM heap size, used for both `-Xms` and `-Xmx`. Set to 50-75% of available RAM. | str | no | 1G |
| `kafka_opts` | Additional JVM flags. Accepts a list of strings or a single string. | raw | no | [] |
| `kafka_node_roles` | Roles this node runs. `broker` and `controller` together make a combined node, either one alone makes a dedicated node. At least one host in the play must be a controller. | list of 'str' | no | ['broker', 'controller'] |
| `kafka_listeners` | Override the auto-derived listener list. Empty means the role generates listeners from the node roles and security state (broker `9092`, controller `9093`). | list of 'str' | no | [] |
| `kafka_inter_broker_listener_name` | Override the inter-broker listener name. Auto-derived from the security state when empty (`PLAINTEXT` or `SSL`). | str | no |  |
| `kafka_num_network_threads` | Number of threads for network requests. Increase for high-throughput clusters. | int | no | 3 |
| `kafka_num_io_threads` | Number of threads for I/O operations. | int | no | 8 |
| `kafka_socket_send_buffer_bytes` | Socket send buffer size in bytes. | int | no | 102400 |
| `kafka_socket_receive_buffer_bytes` | Socket receive buffer size in bytes. | int | no | 102400 |
| `kafka_socket_request_max_bytes` | Maximum allowed request size in bytes (100 MiB by default). | int | no | 104857600 |
| `kafka_security_enabled` | Master switch. When `false`, all listeners use `PLAINTEXT` and neither TLS nor SASL tasks run. | bool | no | False |
| `kafka_tls_enabled` | Enable TLS on broker and controller listeners. Requires `kafka_security_enabled=true`. | bool | no | False |
| `kafka_tls_mode` | How PEM material reaches the broker hosts. `custom` copies files supplied on the control node, `pki_agent` reads files written locally by the `axonops.axonops.pki_agent` role, `generate` creates a self-signed CA and per-host certificates (development only). | str | no | custom |
| `kafka_tls_client_auth` | Client authentication on TLS listeners. `required` is mTLS, `requested` validates a client certificate if one is presented, `none` is server authentication only. | str | no | required |
| `kafka_tls_cert` | (`kafka_tls_mode=custom`) Path to the PEM certificate on the control node. | str | no |  |
| `kafka_tls_key` | (`kafka_tls_mode=custom`) Path to the PEM private key on the control node. | str | no |  |
| `kafka_tls_ca` | (`kafka_tls_mode=custom`) Path to the PEM CA certificate on the control node. | str | no |  |
| `kafka_tls_key_password` | (`kafka_tls_mode=custom`) Password for the private key, if encrypted. Leave empty for unencrypted keys. | str | no |  |
| `kafka_tls_pki_cert_path` | (`kafka_tls_mode=pki_agent`) Path on the broker host where `pki_agent` wrote the certificate PEM file. | str | no | /opt/tls/kafka/cert.pem |
| `kafka_tls_pki_key_path` | (`kafka_tls_mode=pki_agent`) Path on the broker host where `pki_agent` wrote the key PEM file. | str | no | /opt/tls/kafka/key.pem |
| `kafka_tls_pki_ca_path` | (`kafka_tls_mode=pki_agent`) Path on the broker host where `pki_agent` wrote the CA PEM file. | str | no | /opt/tls/kafka/ca.pem |
| `kafka_tls_generate_ca_cn` | (`kafka_tls_mode=generate`) Common name for the generated CA certificate. Development only. | str | no | Kafka Dev CA |
| `kafka_tls_generate_validity_days` | (`kafka_tls_mode=generate`) Validity of the generated certificates in days. | int | no | 3650 |
| `kafka_tls_generate_local_dir` | (`kafka_tls_mode=generate`) Control-node directory used to stage the generated CA between hosts. Defaults to `/tmp/kafka-tls-<cluster>`, where the cluster is `kafka_axonops_cluster_name` or `dev`. | str | no | derived, see description |
| `kafka_tls_remote_dir` | Directory on the broker hosts the PEM files are read from. For `custom` and `generate` modes the role places the files here; `pki_agent` mode reads the `kafka_tls_pki_cert_path`, `kafka_tls_pki_key_path` and `kafka_tls_pki_ca_path` paths directly. | str | no | /etc/kafka/tls |
| `kafka_sasl_enabled` | Enable SASL authentication. Requires `kafka_security_enabled=true`. | bool | no | False |
| `kafka_sasl_mechanism` | SASL mechanism for client and inter-broker authentication. `SCRAM-SHA-512` and `SCRAM-SHA-256` are bootstrapped at format time. `PLAIN` keeps credentials in the JAAS config and should only be used with TLS. The CONTROLLER listener always uses PLAIN. | str | no | SCRAM-SHA-512 |
| `kafka_sasl_inter_broker_user` | Username for inter-broker and broker-to-controller traffic. Added to `super.users` automatically. | str | no | kafka-admin |
| `kafka_sasl_inter_broker_password` | Password for `kafka_sasl_inter_broker_user`. Store in Ansible Vault. | str | no |  |
| `kafka_sasl_users` | Additional SCRAM users created with `kafka-configs.sh` after first start. Ignored when `kafka_sasl_mechanism=PLAIN`. | list of dicts of 'kafka_sasl_users' options | no | [] |
| `kafka_sasl_plain_users` | Static credentials for the PLAIN mechanism, embedded in the JAAS config. Must include the inter-broker user. Ignored when a SCRAM mechanism is used. | list of dicts of 'kafka_sasl_plain_users' options | no | [] |
| `kafka_acl_enabled` | Enable the `StandardAuthorizer`. Requires `kafka_security_enabled=true`. The inter-broker user is always a super user. | bool | no | False |
| `kafka_acl_super_users` | Additional principals granted super-user privileges, for example `User:admin`. The inter-broker user is appended automatically, do not list it again. | list of 'str' | no | [] |
| `kafka_acl_allow_everyone_if_no_acl` | When `false`, access is denied when no matching ACL exists. Set `true` only for development. | bool | no | False |
| `kafka_acls` | Declarative ACL rules applied with `kafka-acls.sh` after the broker starts. | list of dicts of 'kafka_acls' options | no | [] |
| `kafka_num_partitions` | Default number of partitions for auto-created topics. | int | no | 1 |
| `kafka_replication_factor` | Default replication factor. Set to `3` for production clusters. | int | no | 1 |
| `kafka_offsets_topic_replication_factor` | Replication factor for `__consumer_offsets`. Set to `3` for production. | int | no | 1 |
| `kafka_transaction_state_log_replication_factor` | Replication factor for `__transaction_state`. Set to `3` for production. | int | no | 1 |
| `kafka_transaction_state_log_min_isr` | Minimum in-sync replicas for `__transaction_state`. Set to `2` for production. | int | no | 1 |
| `kafka_log_retention_hours` | Retain topic data for this many hours (168 is 7 days). | int | no | 168 |
| `kafka_log_retention_bytes` | Maximum retained bytes per partition. `-1` disables the byte-based limit. | int | no | -1 |
| `kafka_log_segment_bytes` | Maximum size of a single log segment file in bytes (1 GiB by default). | int | no | 1073741824 |
| `kafka_log_retention_check_interval_ms` | How often the log cleaner checks for segments to delete, in milliseconds. | int | no | 300000 |
| `kafka_start_on_install` | Start the Kafka service during the play. Leaving this `false` and starting Kafka manually after validating the cluster is recommended. SCRAM users, ACLs and topics are only applied when this is `true`. | bool | no | False |
| `kafka_start_on_boot` | Enable the Kafka service at boot. | bool | no | False |
| `kafka_configure_firewall` | Open Kafka ports in `firewalld` or `ufw` if either is active. Opens 9092 (broker) and 9093 (controller) only for the roles this node runs. | bool | no | True |
| `kafka_topics` | Topics to create if they do not already exist. Requires `kafka_start_on_install=true` or a running broker. | list of dicts of 'kafka_topics' options | no | [] |
| `kafka_additional_config` | Key/value pairs appended verbatim to `server.properties`. Use for any Kafka property not exposed as a dedicated variable. Do not put secrets here, the values are not hidden from logs. | dict | no |  |
| `kafka_axonops_agent_enabled` | Install and configure the AxonOps agent on Kafka nodes. Requires `kafka_axonops_org` and `kafka_axonops_cluster_name`. | bool | no | False |
| `kafka_axonops_server_host` | AxonOps server host. Defaults to the SaaS endpoint. Override for self-hosted AxonOps server deployments. | str | no | agents.axonops.cloud |
| `kafka_axonops_agent_server_port` | AxonOps server port. Auto-derived from `kafka_axonops_server_host`: `443` for SaaS, `1888` otherwise. | str | no | derived, see description |
| `kafka_axonops_java_agent` | Kafka Java agent package name. | str | no | axon-kafka4-agent |
| `kafka_axonops_sasl_user` | SASL username the AxonOps agent uses for its Kafka admin client. Defaults to `kafka_sasl_inter_broker_user`. Override to use a dedicated lower-privileged identity. | str | no | derived, see description |
| `kafka_axonops_sasl_password` | SASL password for `kafka_axonops_sasl_user`. Defaults to `kafka_sasl_inter_broker_password`. | str | no | derived, see description |
| `kafka_axonops_client_properties_path` | Path on the broker where the agent client properties file is written when security is enabled. | str | no | /etc/axonops/kafka_client.properties |
| `kafka_kconduit_enabled` | Install the Kconduit Kafka CLI client ([https://github.com/digitalis-io/kconduit]). | bool | no | False |
| `kafka_kconduit_version` | Kconduit release version to install. | str | no | 0.0.4 |
| `kafka_kconduit_arch` | Kconduit release architecture, derived from `ansible_architecture`: `arm64` on aarch64, `amd64` otherwise. | str | no | derived, see description |
| `kafka_kconduit_pkg_ext` | Kconduit package extension, derived from `ansible_os_family`: `rpm` on RedHat, `deb` otherwise. | str | no | derived, see description |
| `kafka_kconduit_download_url` | Kconduit package download URL, built from the version, architecture and extension. | str | no | derived, see description |
| `kafka_node_ip` | IP this node advertises in `advertised.listeners`. Defaults to `ansible_default_ipv4.address`. Override for multi-homed hosts. | str | no |  |
| `kafka_cluster_id` | KRaft cluster UUID. Auto-generated and persisted to disk on first format when unset. Set to force a specific UUID. | str | no |  |
| `kafka_checksum` | Checksum of the Kafka archive in `algorithm:value` form. Fetched from the Apache download site when unset. | str | no |  |
| `kafka_axonops_org` | Organisation name in AxonOps. Required when `kafka_axonops_agent_enabled=true`. | str | no |  |
| `kafka_axonops_key` | AxonOps SaaS API key. Required when connecting to `agents.axonops.cloud`. | str | no |  |
| `kafka_axonops_cluster_name` | Cluster name shown in AxonOps. Required when `kafka_axonops_agent_enabled=true`, the Kafka Java agent fails without it. | str | no |  |
| `kafka_axonops_agent_version` | Pin the AxonOps agent version. Leave unset to install the latest available. | str | no |  |
| `kafka_axonops_java_agent_version` | Pin the Kafka Java agent version. Leave unset to install the latest available. | str | no |  |

#### Options for `main > kafka_sasl_users`

|Option|Description|Type|Required|Default|
|---|---|---|---|---|
| `name` | Username. | str | yes |  |
| `password` | Password for the SCRAM user. | str | yes |  |

#### Options for `main > kafka_sasl_plain_users`

|Option|Description|Type|Required|Default|
|---|---|---|---|---|
| `name` | Username. | str | yes |  |
| `password` | Password for the PLAIN user. | str | yes |  |

#### Options for `main > kafka_acls`

|Option|Description|Type|Required|Default|
|---|---|---|---|---|
| `principal` | Principal, for example `User:app1`. | str | yes |  |
| `operation` | Operation the rule applies to, case-insensitive. One of: Read, Write, Create, Delete, Alter, Describe, ClusterAction, AlterConfigs, DescribeConfigs, IdempotentWrite, All. | str | yes |  |
| `resource_type` | Type of resource the rule applies to, case-insensitive. One of: Topic, Group, Cluster, TransactionalId, DelegationToken. | str | yes |  |
| `resource_name` | Resource name, or `*` for all. Required for every resource type except `Cluster`. | str | no |  |
| `permission` | Whether the rule allows or denies the operation, case-insensitive. One of: Allow, Deny. | str | no | Allow |
| `host` | Client host the rule applies to. | str | no | * |
| `pattern_type` | How `kafka_acls[].resource_name` is matched, case-insensitive. One of: LITERAL, PREFIXED. | str | no | LITERAL |

#### Options for `main > kafka_topics`

|Option|Description|Type|Required|Default|
|---|---|---|---|---|
| `name` | Topic name. | str | yes |  |
| `partitions` | Number of partitions. Defaults to `kafka_num_partitions`. | int | no |  |
| `replication_factor` | Replication factor. Defaults to `kafka_replication_factor`. | int | no |  |
| `config` | Topic-level configuration, for example `retention_ms`. | dict | no |  |

#### Choices for `main > kafka_node_roles`

- `broker`
- `controller`

#### Choices for `main > kafka_tls_mode`

- `custom`
- `pki_agent`
- `generate`

#### Choices for `main > kafka_tls_client_auth`

- `required`
- `requested`
- `none`

#### Choices for `main > kafka_sasl_mechanism`

- `SCRAM-SHA-512`
- `SCRAM-SHA-256`
- `PLAIN`

<!-- END_ANSIBLE_DOCS -->

## Upgrade Notes

### Argument validation and internal variable rename

Role input is validated against `meta/argument_specs.yml`. A wrong type, an unknown choice (for example `kafka_tls_mode: bogus`) or a missing `kafka_node_id` now fails before any task runs. ansible-core 2.12 or later is required.

The internal variables are renamed from a double underscore after `kafka` to a leading underscore, for example the home path variable is now `_kafka_home`. They are not part of the public interface; inventories that overrode them must drop those overrides. No public variable changed name.

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
