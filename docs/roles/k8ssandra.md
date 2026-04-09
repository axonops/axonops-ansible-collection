# K8ssandra Role

## Overview

The `k8ssandra` role deploys and manages Apache Cassandra 5.x clusters on Kubernetes using the [K8ssandra](https://k8ssandra.io/) operator with [AxonOps](https://axonops.com/) container images for integrated monitoring. It handles the full lifecycle: installing cert-manager, the k8ssandra-operator, and deploying one or more `K8ssandraCluster` custom resources.

## Requirements

- Ansible 2.10 or higher
- A running Kubernetes cluster with `kubectl` configured
- The `kubernetes.core` Ansible collection (`ansible-galaxy collection install kubernetes.core`)
- Python `kubernetes` package (`pip install kubernetes`)
- Helm 3 installed on the control node
- Only **Cassandra 5.x** is supported

## How It Works

The role performs three main steps:

1. **cert-manager** — Installs via Helm (required by the k8ssandra-operator for webhook certificates)
2. **k8ssandra-operator** — Installs via Helm and waits for it to become ready
3. **Cassandra clusters** — Deploys `K8ssandraCluster` CRs using AxonOps container images

Steps 1 and 2 can be skipped if cert-manager or the operator are already installed.

## Role Variables

### Helm Prerequisites

| Variable | Default | Description |
|----------|---------|-------------|
| `k8ssandra_install_cert_manager` | `true` | Install cert-manager via Helm |
| `k8ssandra_cert_manager_version` | `v1.20.1` | cert-manager Helm chart version |
| `k8ssandra_cert_manager_namespace` | `cert-manager` | Namespace for cert-manager |
| `k8ssandra_install_operator` | `true` | Install k8ssandra-operator via Helm |
| `k8ssandra_operator_version` | `v1.29.0` | k8ssandra-operator image tag |
| `k8ssandra_operator_namespace` | `k8ssandra-operator` | Namespace for the operator |
| `k8ssandra_operator_cluster_scoped` | `true` | Enable cluster-scoped operator |
| `k8ssandra_wait_for_operator` | `true` | Wait for operator readiness before deploying clusters |
| `k8ssandra_operator_wait_timeout` | `300` | Timeout in seconds for operator readiness |

### Cluster Defaults

These defaults apply to all clusters unless overridden per-cluster.

| Variable | Default | Description |
|----------|---------|-------------|
| `k8ssandra_cassandra_version` | `5.0.6` | Cassandra version (must be 5.x) |
| `k8ssandra_image` | `ghcr.io/axonops/k8ssandra/cassandra` | AxonOps container image |
| `k8ssandra_dc_name` | `dc1` | Default datacenter name |
| `k8ssandra_dc_size` | `3` | Default number of nodes per datacenter |
| `k8ssandra_storage_class` | `""` | Kubernetes StorageClass (empty = cluster default) |
| `k8ssandra_storage_size` | `10Gi` | Cassandra data volume size |
| `k8ssandra_axonops_storage_size` | `512Mi` | AxonOps data volume size |
| `k8ssandra_cpu_limit` | `1` | CPU limit per pod |
| `k8ssandra_cpu_request` | `1` | CPU request per pod |
| `k8ssandra_memory_limit` | `2Gi` | Memory limit per pod |
| `k8ssandra_memory_request` | `1Gi` | Memory request per pod |
| `k8ssandra_heap_size` | `1G` | JVM heap size (initial and max) |
| `k8ssandra_soft_pod_anti_affinity` | `true` | Enable soft pod anti-affinity |

### AxonOps Agent Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `k8ssandra_axon_agent_org` | `""` | **Required.** AxonOps organisation identifier |
| `k8ssandra_axon_agent_key` | `""` | **Required.** AxonOps API key |
| `k8ssandra_axon_agent_server_host` | `agents.axonops.cloud` | AxonOps server hostname. Use `agents.axonops.cloud` for SaaS or your on-prem hostname |
| `k8ssandra_axon_agent_server_port` | Auto-detected | `443` for SaaS, `1888` for on-prem |

### Cluster Definition (`k8ssandra_clusters`)

`k8ssandra_clusters` is a list. Each entry creates one `K8ssandraCluster` CR. There are two modes:

#### Simple Mode

Provide basic settings and the role generates the full CR:

| Per-Cluster Key | Falls Back To | Description |
|----------------|---------------|-------------|
| `name` | — | **Required.** Cluster name |
| `namespace` | `k8ssandra_operator_namespace` | Kubernetes namespace |
| `cassandra_version` | `k8ssandra_cassandra_version` | Cassandra version |
| `image` | `k8ssandra_image` | Container image |
| `image_tag` | Cassandra version | Image tag |
| `dc_name` | `k8ssandra_dc_name` | Datacenter name |
| `dc_size` | `k8ssandra_dc_size` | Number of nodes |
| `storage_class` | `k8ssandra_storage_class` | StorageClass |
| `storage_size` | `k8ssandra_storage_size` | Data volume size |
| `axonops_storage_size` | `k8ssandra_axonops_storage_size` | AxonOps volume size |
| `cpu_limit` | `k8ssandra_cpu_limit` | CPU limit |
| `cpu_request` | `k8ssandra_cpu_request` | CPU request |
| `memory_limit` | `k8ssandra_memory_limit` | Memory limit |
| `memory_request` | `k8ssandra_memory_request` | Memory request |
| `heap_size` | `k8ssandra_heap_size` | JVM heap size |
| `axon_agent_org` | `k8ssandra_axon_agent_org` | AxonOps org |
| `axon_agent_key` | `k8ssandra_axon_agent_key` | AxonOps API key |
| `axon_agent_server_host` | `k8ssandra_axon_agent_server_host` | AxonOps server host |
| `axon_agent_server_port` | `k8ssandra_axon_agent_server_port` | AxonOps server port |
| `extra_env` | — | Additional env vars for the cassandra container |
| `cassandra_config` | — | Additional cassandraYaml config (dict) |
| `labels` | — | Labels for the CR metadata |
| `annotations` | — | Annotations for the CR metadata |
| `additional_datacenters` | — | List of extra DCs (see Multi-DC example) |

#### Custom Mode

Provide the full `K8ssandraCluster` spec directly:

| Per-Cluster Key | Description |
|----------------|-------------|
| `name` | **Required.** Cluster name (for labelling) |
| `custom_spec` | Full K8ssandraCluster YAML as a dict |

## Dependencies

- `kubernetes.core` Ansible collection

## Example Playbooks

### Basic Single Cluster

Deploy a 3-node Cassandra 5.x cluster with AxonOps monitoring:

```yaml
- name: Deploy K8ssandra cluster
  hosts: localhost
  connection: local
  gather_facts: false

  vars:
    k8ssandra_axon_agent_org: "MY-ORG"
    k8ssandra_axon_agent_key: "MY-KEY"

    k8ssandra_clusters:
      - name: my-cluster
        cassandra_version: "5.0.6"
        dc_name: dc1
        dc_size: 3
        storage_size: 10Gi
        heap_size: 1G

  roles:
    - axonops.axonops.k8ssandra
```

### Production Cluster with Custom Resources

```yaml
- name: Deploy production K8ssandra cluster
  hosts: localhost
  connection: local
  gather_facts: false

  vars:
    k8ssandra_axon_agent_org: "MY-ORG"
    k8ssandra_axon_agent_key: "MY-KEY"

    k8ssandra_clusters:
      - name: production
        cassandra_version: "5.0.6"
        dc_name: us-east-1
        dc_size: 6
        storage_size: 100Gi
        storage_class: gp3
        heap_size: 8G
        cpu_limit: 8
        cpu_request: 4
        memory_limit: 16Gi
        memory_request: 12Gi

  roles:
    - axonops.axonops.k8ssandra
```

### Multi-Datacenter Cluster

```yaml
- name: Deploy multi-DC K8ssandra cluster
  hosts: localhost
  connection: local
  gather_facts: false

  vars:
    k8ssandra_axon_agent_org: "MY-ORG"
    k8ssandra_axon_agent_key: "MY-KEY"

    k8ssandra_clusters:
      - name: global-cluster
        cassandra_version: "5.0.6"
        dc_name: us-east-1
        dc_size: 3
        storage_size: 50Gi
        heap_size: 4G
        additional_datacenters:
          - name: eu-west-1
            size: 3
            heap_size: 4G
            storage_size: 50Gi

  roles:
    - axonops.axonops.k8ssandra
```

### Multiple Clusters

Deploy several independent clusters in one run:

```yaml
- name: Deploy multiple K8ssandra clusters
  hosts: localhost
  connection: local
  gather_facts: false

  vars:
    k8ssandra_axon_agent_org: "MY-ORG"
    k8ssandra_axon_agent_key: "MY-KEY"

    k8ssandra_clusters:
      - name: cluster-prod
        dc_name: us-east-1
        dc_size: 6
        storage_size: 100Gi
        heap_size: 8G

      - name: cluster-staging
        dc_name: us-east-1
        dc_size: 3
        storage_size: 20Gi
        heap_size: 2G

  roles:
    - axonops.axonops.k8ssandra
```

### On-Prem AxonOps Server

```yaml
- name: Deploy K8ssandra with on-prem AxonOps
  hosts: localhost
  connection: local
  gather_facts: false

  vars:
    k8ssandra_axon_agent_org: "MY-ORG"
    k8ssandra_axon_agent_key: "MY-KEY"
    k8ssandra_axon_agent_server_host: "axonops.internal.example.com"
    # Port auto-detected as 1888 for non-SaaS hosts

    k8ssandra_clusters:
      - name: onprem-cluster
        dc_size: 3
        storage_size: 50Gi

  roles:
    - axonops.axonops.k8ssandra
```

### Custom Spec Mode

Provide a full `K8ssandraCluster` manifest when you need options not exposed by simple mode:

```yaml
- name: Deploy K8ssandra with custom spec
  hosts: localhost
  connection: local
  gather_facts: false

  vars:
    k8ssandra_clusters:
      - name: custom-cluster
        custom_spec: "{{ lookup('file', 'my-cluster.yaml') | from_yaml }}"

  roles:
    - axonops.axonops.k8ssandra
```

### Extra Environment Variables

Pass additional environment variables to the Cassandra container:

```yaml
- name: Deploy K8ssandra with extra env vars
  hosts: localhost
  connection: local
  gather_facts: false

  vars:
    k8ssandra_axon_agent_org: "MY-ORG"
    k8ssandra_axon_agent_key: "MY-KEY"

    k8ssandra_clusters:
      - name: my-cluster
        dc_size: 3
        extra_env:
          - name: CASSANDRA_GC_STDOUT
            value: "true"
          - name: CUSTOM_SETTING
            value: "my-value"

  roles:
    - axonops.axonops.k8ssandra
```

### Skip Operator Installation

If cert-manager and k8ssandra-operator are already installed:

```yaml
- name: Deploy clusters only (operator pre-installed)
  hosts: localhost
  connection: local
  gather_facts: false

  vars:
    k8ssandra_install_cert_manager: false
    k8ssandra_install_operator: false

    k8ssandra_axon_agent_org: "MY-ORG"
    k8ssandra_axon_agent_key: "MY-KEY"

    k8ssandra_clusters:
      - name: my-cluster
        dc_size: 3

  roles:
    - axonops.axonops.k8ssandra
```

## Tags

| Tag | Description |
|-----|-------------|
| `cert-manager` | cert-manager installation tasks only |
| `operator` | k8ssandra-operator installation tasks only |
| `clusters` | Cluster deployment tasks only |

## Notes

- **Cassandra 5.x only**: This role validates that `cassandra_version` starts with `5.`. Cassandra 4.x is not supported on k8ssandra with AxonOps containers.
- **AxonOps containers**: All clusters use the AxonOps k8ssandra container image (`ghcr.io/axonops/k8ssandra/cassandra`), which includes the AxonOps agent, Java agent, and cqlai pre-installed.
- **AxonOps data volume**: An extra PVC (`axonops-data`) is always mounted at `/var/lib/axonops` for agent data persistence.
- **StorageClass**: Leave `k8ssandra_storage_class` empty to use the cluster's default StorageClass.
- **Agent configuration**: The AxonOps agent is configured via environment variables (`AXON_AGENT_ORG`, `AXON_AGENT_KEY`, `AXON_AGENT_SERVER_HOST`, `AXON_AGENT_SERVER_PORT`) injected into the Cassandra container.
- **Idempotency**: The role is idempotent. Running it again will update existing resources if the spec has changed.

## License

See the main collection LICENSE file.

## Author

AxonOps Limited
