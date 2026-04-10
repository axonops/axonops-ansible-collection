# AxonOps Ansible Collection - Role Documentation

This directory contains detailed documentation for each role in the AxonOps Ansible Collection.

## Available Roles

### Core AxonOps Components

#### [agent](agent.md)
Installs and configures the AxonOps Agent on Cassandra nodes for monitoring and metric collection.

**Use when**: You want to monitor your Cassandra cluster with AxonOps (required on all Cassandra nodes).

#### [server](server.md)
Installs and configures the AxonOps Server for self-hosted deployments.

**Use when**: You're deploying AxonOps on-premises instead of using the SaaS offering.

#### [dash](dash.md)
Installs and configures the AxonOps Dashboard web interface.

**Use when**: You're deploying a self-hosted AxonOps Server and need the web UI (typically installed alongside the server).

#### [configurations](configurations.md)
Configures alerts, integrations, and monitoring settings for AxonOps.

**Use when**: You need to automate the configuration of alerts, Slack/PagerDuty integrations, or backup policies.

### Kubernetes

#### [k8ssandra](k8ssandra.md)
Deploys and manages Cassandra 5.x clusters on Kubernetes using the K8ssandra operator with AxonOps container images.

**Use when**: You want to run Cassandra on Kubernetes with AxonOps monitoring. Handles cert-manager, k8ssandra-operator, and cluster CR deployment.

#### [strimzi](strimzi.md)
Deploys and manages Apache Kafka clusters on Kubernetes using the Strimzi operator with AxonOps container images.

**Use when**: You want to run Kafka on Kubernetes with AxonOps monitoring. Handles Strimzi operator, broker/controller node pools, and optional Kafka Connect.

### Infrastructure Components

#### [cassandra](cassandra.md)
Installs and configures Apache Cassandra (versions 3.11, 4.x, and 5.x).

**Use when**: You need to deploy new Cassandra nodes or manage existing installations.

#### [opensearch](opensearch.md)
Installs and configures OpenSearch as the search backend for AxonOps Server.

**Use when**: Deploying a self-hosted AxonOps Server. OpenSearch is the preferred search backend for on-premises deployments. It provides full TLS security, multi-node clustering, and active open-source maintenance.

#### [elastic](elastic.md)
Installs and configures Elasticsearch for AxonOps Server configuration storage.

**Use when**: You have an existing Elasticsearch deployment or are migrating from an older AxonOps installation. For new on-premises deployments, prefer `opensearch`.

#### [java](java.md)
Installs Java (OpenJDK or Azul Zulu) on target systems.

**Use when**: Deploying Cassandra, Elasticsearch, or any Java-dependent component.

### Utility Roles

#### [preflight](preflight.md)
Performs pre-installation checks to ensure systems meet requirements.

**Use when**: Before deploying Cassandra or AxonOps components to validate system readiness.

## Quick Reference

| Role | Purpose | Typically Used With |
|------|---------|-------------------|
| **agent** | Monitor Cassandra clusters | Cassandra nodes |
| **server** | Self-hosted AxonOps backend | OpenSearch (preferred) or Elastic, Cassandra (optional) |
| **dash** | Web UI for AxonOps | Server |
| **configurations** | Alert configuration | Server |
| **k8ssandra** | Cassandra on Kubernetes | Kubernetes cluster |
| **strimzi** | Kafka on Kubernetes | Kubernetes cluster |
| **cassandra** | Apache Cassandra installation | Agent, Java |
| **opensearch** | OpenSearch installation (preferred for on-premises) | Server |
| **elastic** | Elasticsearch installation (legacy / existing deployments) | Server |
| **java** | Java installation | Cassandra, Elastic |
| **preflight** | System validation | Before any installation |

## Common Deployment Patterns

### Pattern 1: Monitor Existing Cassandra Cluster (SaaS)

Deploy AxonOps Agent on existing Cassandra nodes to monitor with AxonOps SaaS:

```yaml
- hosts: cassandra
  roles:
    - role: axonops.axonops.agent
```

**Roles needed**: `axonops.axonops.agent`

**See**: [agent.md](agent.md)

---

### Pattern 2: New Cassandra Cluster with Monitoring (SaaS)

Deploy new Cassandra cluster with AxonOps monitoring:

```yaml
- hosts: cassandra
  roles:
    - role: axonops.axonops.preflight
    - role: axonops.axonops.java
    - role: axonops.axonops.agent
    - role: axonops.axonops.cassandra
```

**Roles needed**: `axonops.axonops.preflight`, `axonops.axonops.java`, `axonops.axonops.agent`, `axonops.axonops.cassandra`

**See**: [cassandra.md](cassandra.md), [agent.md](agent.md), [java.md](java.md), [preflight.md](preflight.md)

---

### Pattern 3: Self-Hosted AxonOps Server with OpenSearch (recommended)

Deploy a complete self-hosted AxonOps stack using OpenSearch as the search backend.
OpenSearch is preferred for new on-premises deployments:

```yaml
- hosts: axon-server
  vars:
    opensearch_cluster_name: axonops
    opensearch_cluster_type: single-node
    opensearch_admin_password: "{{ vault_opensearch_admin_password }}"
    opensearch_domain_name: example.com
    axon_server_searchdb_hosts:
      - "https://127.0.0.1:9200"
    axon_server_searchdb_username: admin
    axon_server_searchdb_password: "{{ vault_opensearch_admin_password }}"
    axon_server_searchdb_tls_skip_verify: true
  roles:
    - role: axonops.axonops.opensearch
    - role: axonops.axonops.cassandra  # Optional: for metrics storage
    - role: axonops.axonops.server
    - role: axonops.axonops.dash
```

**Roles needed**: `axonops.axonops.opensearch`, `axonops.axonops.server`, `axonops.axonops.dash`, optionally `axonops.axonops.cassandra`

**See**: [server.md](server.md), [opensearch.md](opensearch.md), [dash.md](dash.md)

---

### Pattern 3b: Self-Hosted AxonOps Server with Elasticsearch (legacy)

For existing deployments using Elasticsearch:

```yaml
- hosts: axon-server
  roles:
    - role: axonops.axonops.java
    - role: axonops.axonops.elastic
    - role: axonops.axonops.cassandra  # Optional: for metrics storage
    - role: axonops.axonops.server
    - role: axonops.axonops.dash
```

**Roles needed**: `axonops.axonops.java`, `axonops.axonops.elastic`, `axonops.axonops.server`, `axonops.axonops.dash`, optionally `axonops.axonops.cassandra`

**See**: [server.md](server.md), [elastic.md](elastic.md), [dash.md](dash.md)

---

### Pattern 4: Complete Infrastructure

Deploy both AxonOps Server and a monitored Cassandra cluster. OpenSearch is the preferred search backend for on-premises deployments:

**Server host (with OpenSearch)**:
```yaml
- hosts: axon-server
  vars:
    opensearch_cluster_name: axonops
    opensearch_cluster_type: single-node
    opensearch_admin_password: "{{ vault_opensearch_admin_password }}"
    opensearch_domain_name: example.com
    axon_server_searchdb_hosts:
      - "https://127.0.0.1:9200"
    axon_server_searchdb_username: admin
    axon_server_searchdb_password: "{{ vault_opensearch_admin_password }}"
    axon_server_searchdb_tls_skip_verify: true
  roles:
    - role: axonops.axonops.opensearch
    - role: axonops.axonops.cassandra
    - role: axonops.axonops.agent
    - role: axonops.axonops.server
    - role: axonops.axonops.dash
```

**Cassandra hosts**:
```yaml
- hosts: cassandra
  roles:
    - role: axonops.axonops.preflight
    - role: axonops.axonops.java
    - role: axonops.axonops.agent
    - role: axonops.axonops.cassandra
```

**Roles needed**: `axonops.axonops.opensearch`, `axonops.axonops.cassandra`, `axonops.axonops.agent`, `axonops.axonops.server`, `axonops.axonops.dash` (server host); `axonops.axonops.preflight`, `axonops.axonops.java`, `axonops.axonops.agent`, `axonops.axonops.cassandra` (Cassandra hosts)

For existing Elasticsearch deployments, replace the `opensearch` role with `axonops.axonops.java` and `axonops.axonops.elastic`, and set `axon_server_searchdb_hosts` to `["http://127.0.0.1:9200"]`.

---

### Pattern 5: Cassandra on Kubernetes (K8ssandra)

Deploy Cassandra 5.x on Kubernetes with AxonOps monitoring:

```yaml
- hosts: localhost
  connection: local
  vars:
    k8ssandra_axon_agent_org: "MY-ORG"
    k8ssandra_axon_agent_key: "MY-KEY"
    k8ssandra_clusters:
      - name: my-cluster
        dc_size: 3
        storage_size: 10Gi
  roles:
    - role: axonops.axonops.k8ssandra
```

**Roles needed**: `axonops.axonops.k8ssandra`

**See**: [k8ssandra.md](k8ssandra.md)

---

### Pattern 6: Kafka on Kubernetes (Strimzi)

Deploy Kafka on Kubernetes with AxonOps monitoring:

```yaml
- hosts: localhost
  connection: local
  vars:
    strimzi_axon_agent_org: "MY-ORG"
    strimzi_axon_agent_key: "MY-KEY"
    strimzi_clusters:
      - name: my-kafka
        namespace: kafka
        broker_replicas: 3
        controller_replicas: 3
  roles:
    - role: axonops.axonops.strimzi
```

**Roles needed**: `axonops.axonops.strimzi`

**See**: [strimzi.md](strimzi.md)

---

### Pattern 7: Alert Configuration

Configure alerts and integrations for existing AxonOps deployment:

```yaml
- hosts: localhost
  roles:
    - role: axonops.axonops.configurations
```

**Roles needed**: `axonops.axonops.configurations`

**See**: [configurations.md](configurations.md)

## Getting Started

1. **Choose your deployment pattern** from the list above
2. **Read the documentation** for each role you'll use
3. **Review the example playbooks** in each role's documentation
4. **Customize variables** to match your environment
5. **Run preflight checks** before deploying Cassandra
6. **Deploy in stages** (infrastructure first, then applications, then configuration)

## Additional Resources

- [Main README](../../README.md) - Collection overview and installation
- [Examples Directory](../../examples/) - Complete example playbooks
- [AxonOps Documentation](https://docs.axonops.com/) - Official AxonOps documentation
- [ALERTS.md](../../ALERTS.md) - Alert configuration guide

## Support

For issues, questions, or contributions:
- GitHub Issues: [axonops-ansible-collection](https://github.com/axonops/axonops-ansible-collection/issues)
- AxonOps Support: [support@axonops.com](mailto:support@axonops.com)
- Community Slack: [axonops.slack.com](https://axonops.slack.com)

## License

See the [LICENSE](../../LICENSE) file in the repository root.
