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

#### [alerts](alerts.md)
Configures alerts, integrations, and monitoring settings for AxonOps.

**Use when**: You need to automate the configuration of alerts, Slack/PagerDuty integrations, or backup policies.

### Infrastructure Components

#### [cassandra](cassandra.md)
Installs and configures Apache Cassandra (versions 3.11, 4.x, and 5.x).

**Use when**: You need to deploy new Cassandra nodes or manage existing installations.

#### [elastic](elastic.md)
Installs and configures Elasticsearch for AxonOps Server configuration storage.

**Use when**: Deploying a self-hosted AxonOps Server (Elasticsearch stores AxonOps configuration data).

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
| **server** | Self-hosted AxonOps backend | Elastic, Cassandra (optional) |
| **dash** | Web UI for AxonOps | Server |
| **alerts** | Alert configuration | Server |
| **cassandra** | Apache Cassandra installation | Agent, Java |
| **elastic** | Elasticsearch installation | Server |
| **java** | Java installation | Cassandra, Elastic |
| **preflight** | System validation | Before any installation |

## Common Deployment Patterns

### Pattern 1: Monitor Existing Cassandra Cluster (SaaS)

Deploy AxonOps Agent on existing Cassandra nodes to monitor with AxonOps SaaS:

```yaml
- hosts: cassandra
  roles:
    - agent
```

**Roles needed**: `agent`

**See**: [agent.md](agent.md)

---

### Pattern 2: New Cassandra Cluster with Monitoring (SaaS)

Deploy new Cassandra cluster with AxonOps monitoring:

```yaml
- hosts: cassandra
  roles:
    - preflight
    - java
    - agent
    - cassandra
```

**Roles needed**: `preflight`, `java`, `agent`, `cassandra`

**See**: [cassandra.md](cassandra.md), [agent.md](agent.md), [java.md](java.md), [preflight.md](preflight.md)

---

### Pattern 3: Self-Hosted AxonOps Server

Deploy complete self-hosted AxonOps stack:

```yaml
- hosts: axon-server
  roles:
    - java
    - elastic
    - cassandra  # Optional: for metrics storage
    - server
    - dash
```

**Roles needed**: `java`, `elastic`, `server`, `dash`, optionally `cassandra`

**See**: [server.md](server.md), [elastic.md](elastic.md), [dash.md](dash.md)

---

### Pattern 4: Complete Infrastructure

Deploy both AxonOps Server and monitored Cassandra cluster:

**Server host**:
```yaml
- hosts: axon-server
  roles:
    - java
    - elastic
    - cassandra
    - agent
    - server
    - dash
```

**Cassandra hosts**:
```yaml
- hosts: cassandra
  roles:
    - preflight
    - java
    - agent
    - cassandra
```

**Roles needed**: All roles

---

### Pattern 5: Alert Configuration

Configure alerts and integrations for existing AxonOps deployment:

```yaml
- hosts: localhost
  roles:
    - alerts
```

**Roles needed**: `alerts`

**See**: [alerts.md](alerts.md)

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
