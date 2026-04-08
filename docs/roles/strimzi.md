# Strimzi Role

## Overview

The `strimzi` role deploys and manages Apache Kafka clusters on Kubernetes using the [Strimzi](https://strimzi.io/) operator with [AxonOps](https://axonops.com/) container images for integrated monitoring. It handles installing the Strimzi operator via Helm and deploying Kafka clusters in KRaft mode (no ZooKeeper) with separate broker and controller node pools.

## Requirements

- Ansible 2.10 or higher
- A running Kubernetes cluster with `kubectl` configured
- The `kubernetes.core` Ansible collection (`ansible-galaxy collection install kubernetes.core`)
- Python `kubernetes` package (`pip install kubernetes`)
- Helm 3 installed on the control node
- KRaft mode only (ZooKeeper is not supported)

## How It Works

The role performs two main steps:

1. **Strimzi operator** — Installs via Helm and waits for the cluster-operator to become ready
2. **Kafka clusters** — For each cluster, deploys:
   - A `KafkaNodePool` for controllers (KRaft)
   - A `KafkaNodePool` for brokers
   - A `Kafka` CR (with KRaft and node-pools annotations enabled)
   - Optionally a `KafkaConnect` CR

Step 1 can be skipped if the Strimzi operator is already installed.

## Role Variables

### Strimzi Operator

| Variable | Default | Description |
|----------|---------|-------------|
| `strimzi_install_operator` | `true` | Install the Strimzi operator via Helm |
| `strimzi_operator_version` | `0.51.0` | Strimzi operator Helm chart version |
| `strimzi_operator_namespace` | `strimzi-system` | Namespace for the operator |
| `strimzi_operator_helm_repo` | `https://strimzi.io/charts/` | Helm repo URL |
| `strimzi_operator_helm_values` | `{}` | Extra Helm values for the operator chart |
| `strimzi_wait_for_operator` | `true` | Wait for operator readiness |
| `strimzi_operator_wait_timeout` | `300` | Timeout in seconds |

### Cluster Defaults

These defaults apply to all clusters unless overridden per-cluster.

| Variable | Default | Description |
|----------|---------|-------------|
| `strimzi_kafka_version` | `4.1.1` | Kafka version |
| `strimzi_image` | `ghcr.io/axonops/strimzi/kafka` | AxonOps container image |
| `strimzi_image_tag` | `0.50.0-4.1.1-2.0.19-0.1.12` | Image tag |
| `strimzi_broker_replicas` | `3` | Number of broker nodes |
| `strimzi_broker_storage_size` | `10Gi` | Broker storage volume size |
| `strimzi_broker_storage_class` | `""` | Broker StorageClass (empty = default) |
| `strimzi_controller_replicas` | `3` | Number of controller nodes |
| `strimzi_controller_storage_size` | `10Gi` | Controller storage volume size |
| `strimzi_controller_storage_class` | `""` | Controller StorageClass (empty = default) |
| `strimzi_default_replication_factor` | `3` | Default topic replication factor |
| `strimzi_min_insync_replicas` | `2` | Minimum in-sync replicas |
| `strimzi_rack_topology_key` | `topology.kubernetes.io/zone` | Topology key for rack awareness |
| `strimzi_kafka_connect_enabled` | `false` | Deploy Kafka Connect |
| `strimzi_kafka_connect_replicas` | `2` | Kafka Connect worker replicas |

### AxonOps Agent Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `strimzi_axon_agent_org` | `""` | **Required.** AxonOps organisation identifier |
| `strimzi_axon_agent_key` | `""` | **Required.** AxonOps API key |
| `strimzi_axon_agent_server_host` | `agents.axonops.cloud` | AxonOps server hostname |
| `strimzi_axon_agent_server_port` | Auto-detected | `443` for SaaS, `1888` for on-prem |
| `strimzi_axon_agent_tls_mode` | Auto-detected | `TLS` for SaaS, `disabled` for on-prem |

### Cluster Definition (`strimzi_clusters`)

`strimzi_clusters` is a list. Each entry creates a Kafka cluster (Kafka CR + KafkaNodePool CRs).

#### Simple Mode

| Per-Cluster Key | Falls Back To | Description |
|----------------|---------------|-------------|
| `name` | — | **Required.** Cluster name |
| `namespace` | `kafka` | Kubernetes namespace |
| `kafka_version` | `strimzi_kafka_version` | Kafka version |
| `image` | `strimzi_image` | Container image |
| `image_tag` | `strimzi_image_tag` | Image tag |
| `broker_replicas` | `strimzi_broker_replicas` | Number of brokers |
| `broker_storage_size` | `strimzi_broker_storage_size` | Broker storage |
| `broker_storage_class` | `strimzi_broker_storage_class` | Broker StorageClass |
| `controller_replicas` | `strimzi_controller_replicas` | Number of controllers |
| `controller_storage_size` | `strimzi_controller_storage_size` | Controller storage |
| `controller_storage_class` | `strimzi_controller_storage_class` | Controller StorageClass |
| `default_replication_factor` | `strimzi_default_replication_factor` | Replication factor |
| `min_insync_replicas` | `strimzi_min_insync_replicas` | Min ISR |
| `rack_topology_key` | `strimzi_rack_topology_key` | Rack awareness key |
| `listeners` | `strimzi_listeners` | Kafka listener configuration |
| `kafka_config` | — | Additional Kafka broker config (dict) |
| `axon_agent_org` | `strimzi_axon_agent_org` | AxonOps org |
| `axon_agent_key` | `strimzi_axon_agent_key` | AxonOps API key |
| `axon_agent_server_host` | `strimzi_axon_agent_server_host` | AxonOps server host |
| `axon_agent_server_port` | `strimzi_axon_agent_server_port` | AxonOps server port |
| `axon_agent_tls_mode` | `strimzi_axon_agent_tls_mode` | AxonOps TLS mode |
| `axon_agent_cluster_name` | `name` | AxonOps cluster name (defaults to Kafka cluster name) |
| `kafka_connect_enabled` | `strimzi_kafka_connect_enabled` | Enable Kafka Connect |
| `kafka_connect_replicas` | `strimzi_kafka_connect_replicas` | Connect worker replicas |
| `broker_extra_env` | — | Extra env vars for broker containers |
| `controller_extra_env` | — | Extra env vars for controller containers |

#### Custom Mode

Provide full Strimzi CRs directly:

| Per-Cluster Key | Description |
|----------------|-------------|
| `name` | **Required.** Cluster name (for labelling) |
| `custom_specs.kafka` | Full Kafka CR as a dict |
| `custom_specs.broker_pool` | Full broker KafkaNodePool CR |
| `custom_specs.controller_pool` | Full controller KafkaNodePool CR |
| `custom_specs.kafka_connect` | Full KafkaConnect CR (optional) |

## Dependencies

- `kubernetes.core` Ansible collection

## Example Playbooks

### Basic Kafka Cluster

Deploy a 3-broker, 3-controller Kafka cluster with AxonOps monitoring:

```yaml
- name: Deploy Strimzi Kafka cluster
  hosts: localhost
  connection: local
  gather_facts: false

  vars:
    strimzi_axon_agent_org: "MY-ORG"
    strimzi_axon_agent_key: "MY-KEY"

    strimzi_clusters:
      - name: my-kafka
        namespace: kafka
        broker_replicas: 3
        controller_replicas: 3
        broker_storage_size: 10Gi

  roles:
    - axonops.axonops.strimzi
```

### Production Cloud Deployment

```yaml
- name: Deploy production Kafka on cloud
  hosts: localhost
  connection: local
  gather_facts: false

  vars:
    strimzi_axon_agent_org: "MY-ORG"
    strimzi_axon_agent_key: "MY-KEY"

    strimzi_clusters:
      - name: prod-kafka
        namespace: kafka
        kafka_version: "4.1.1"
        broker_replicas: 6
        controller_replicas: 3
        broker_storage_size: 100Gi
        broker_storage_class: gp3
        controller_storage_size: 10Gi
        controller_storage_class: gp3
        default_replication_factor: 3
        min_insync_replicas: 2

  roles:
    - axonops.axonops.strimzi
```

### On-Prem AxonOps Server

```yaml
- name: Deploy Kafka with on-prem AxonOps
  hosts: localhost
  connection: local
  gather_facts: false

  vars:
    strimzi_axon_agent_org: "MY-ORG"
    strimzi_axon_agent_key: "not-used"
    strimzi_axon_agent_server_host: "axonops.internal.example.com"
    # Port (1888) and TLS mode (disabled) are auto-detected for non-SaaS hosts

    strimzi_clusters:
      - name: onprem-kafka
        namespace: kafka
        broker_replicas: 3
        controller_replicas: 3
        broker_storage_size: 50Gi

  roles:
    - axonops.axonops.strimzi
```

### Kafka with Connect

```yaml
- name: Deploy Kafka with Kafka Connect
  hosts: localhost
  connection: local
  gather_facts: false

  vars:
    strimzi_axon_agent_org: "MY-ORG"
    strimzi_axon_agent_key: "MY-KEY"

    strimzi_clusters:
      - name: data-pipeline
        namespace: kafka
        broker_replicas: 3
        controller_replicas: 3
        broker_storage_size: 20Gi
        kafka_connect_enabled: true
        kafka_connect_replicas: 2

  roles:
    - axonops.axonops.strimzi
```

### Multiple Clusters

```yaml
- name: Deploy multiple Kafka clusters
  hosts: localhost
  connection: local
  gather_facts: false

  vars:
    strimzi_axon_agent_org: "MY-ORG"
    strimzi_axon_agent_key: "MY-KEY"

    strimzi_clusters:
      - name: prod-events
        namespace: kafka-prod
        broker_replicas: 6
        broker_storage_size: 100Gi

      - name: staging-events
        namespace: kafka-staging
        broker_replicas: 3
        broker_storage_size: 20Gi

  roles:
    - axonops.axonops.strimzi
```

### Skip Operator Installation

```yaml
- name: Deploy clusters only (operator pre-installed)
  hosts: localhost
  connection: local
  gather_facts: false

  vars:
    strimzi_install_operator: false

    strimzi_axon_agent_org: "MY-ORG"
    strimzi_axon_agent_key: "MY-KEY"

    strimzi_clusters:
      - name: my-kafka
        broker_replicas: 3

  roles:
    - axonops.axonops.strimzi
```

### Custom Kafka Config

```yaml
- name: Deploy Kafka with custom broker config
  hosts: localhost
  connection: local
  gather_facts: false

  vars:
    strimzi_axon_agent_org: "MY-ORG"
    strimzi_axon_agent_key: "MY-KEY"

    strimzi_clusters:
      - name: custom-kafka
        broker_replicas: 3
        kafka_config:
          log.retention.hours: 168
          log.segment.bytes: 1073741824
          num.partitions: 12
          auto.create.topics.enable: false

  roles:
    - axonops.axonops.strimzi
```

## Tags

| Tag | Description |
|-----|-------------|
| `operator` | Strimzi operator installation tasks only |
| `clusters` | Kafka cluster deployment tasks only |

## Notes

- **KRaft mode only**: This role always deploys Kafka in KRaft mode (no ZooKeeper). The `strimzi.io/kraft: enabled` and `strimzi.io/node-pools: enabled` annotations are set on every Kafka CR.
- **AxonOps containers**: All clusters use the AxonOps Strimzi container image, which includes the AxonOps Kafka agent pre-installed.
- **JBOD storage**: Storage uses JBOD with a single volume at index `0` (required by AxonOps).
- **Topology awareness**: Controllers use `topologySpreadConstraints` for zone-aware scheduling. The rack topology key is configurable.
- **Logging**: Log4j is configured inline to write to `/var/log/kafka/server.log` with 10MB rolling files.
- **Agent configuration**: The AxonOps agent is configured via environment variables (`AXON_AGENT_ORG`, `AXON_AGENT_KEY`, `AXON_AGENT_SERVER_HOST`, `AXON_AGENT_SERVER_PORT`, `AXON_AGENT_TLS_MODE`, `KAFKA_NODE_TYPE`) injected into each container.
- **Node types**: The `KAFKA_NODE_TYPE` env var is automatically set to `kraft-controller`, `kraft-broker`, or `connect` depending on the pool type.

## License

See the main collection LICENSE file.

## Author

AxonOps Limited
