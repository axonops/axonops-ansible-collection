# Alerts Role

## Overview

The `alerts` role configures alerts, integrations, and monitoring settings for your AxonOps deployment. This role manages metric alerts, backup configurations, service checks, integration with notification services (Slack, PagerDuty), log alerts, and custom dashboards.

## Requirements

- Ansible 2.9 or higher
- AxonOps Server installed and running
- AxonOps API access

## Role Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `org` | Organization name in AxonOps | `mycompany` |
| `cluster` | Cluster name to configure alerts for | `production-cluster` |

**Note**: These variables can also be set via environment variables `AXONOPS_ORG` and `AXONOPS_CLUSTER`.

### Optional Feature Flags

| Variable | Description | Default |
|----------|-------------|---------|
| `adaptive_repair` | Configuration for adaptive repair settings | undefined |
| `agent_disconnection_tolerance` | Agent disconnection tolerance settings | undefined |
| `human_readableid` | Human-readable ID configuration | undefined |

## Dependencies

This role requires a running AxonOps Server with API access.

## Example Playbooks

### Basic Alert Configuration

```yaml
- name: Configure AxonOps Alerts
  hosts: localhost
  vars:
    org: mycompany
    cluster: production-cluster

  roles:
    - role: axonops.axonops.alerts
```

### Using Environment Variables

```yaml
- name: Configure Alerts with Environment Variables
  hosts: localhost
  # Ensure AXONOPS_ORG and AXONOPS_CLUSTER are set in the environment

  roles:
    - role: axonops.axonops.alerts
```

### Configure Specific Alert Types

```yaml
- name: Configure Only Metric Alerts and Backups
  hosts: localhost
  vars:
    org: mycompany
    cluster: production-cluster

  roles:
    - role: axonops.axonops.alerts
      tags:
        - metrics
        - backups
```

### Configure Slack Integration

```yaml
- name: Configure Alerts with Slack Integration
  hosts: localhost
  vars:
    org: mycompany
    cluster: production-cluster

  roles:
    - role: axonops.axonops.alerts
      tags:
        - slack
```

### Configure PagerDuty Integration

```yaml
- name: Configure Alerts with PagerDuty Integration
  hosts: localhost
  vars:
    org: mycompany
    cluster: production-cluster

  roles:
    - role: axonops.axonops.alerts
      tags:
        - pagerduty_integration
```

### Full Alert Stack Configuration

```yaml
- name: Configure Complete Alert Stack
  hosts: localhost
  vars:
    org: mycompany
    cluster: production-cluster
    adaptive_repair:
      enabled: true
    agent_disconnection_tolerance:
      key: enabled
      value: true
    human_readableid:
      enabled: true

  roles:
    - role: axonops.axonops.alerts
```

## Available Tags

The role supports granular control through the following tags:

| Tag | Description |
|-----|-------------|
| `metrics` | Configure metric alerts |
| `backups` | Configure backup settings |
| `service_checks` | Configure service check alerts |
| `slack` | Configure Slack integration |
| `pagerduty_integration` | Configure PagerDuty integration |
| `adaptive_repair` | Configure adaptive repair settings |
| `agent_disconnection_tolerance` | Configure agent disconnection tolerance |
| `commitlogs_archive` | Configure commit log archiving |
| `human_readableid` | Configure human-readable IDs |
| `log_alerts` | Configure log-based alerts |
| `logcollector` | Configure log collector |
| `dashboards` | Import custom dashboards |
| `routes` | Configure alert routing rules |

## Tasks Overview

The role performs the following tasks based on the enabled tags:

1. **Metrics Alerts**: Configure threshold-based alerts for Cassandra metrics
2. **Backup Configuration**: Set up backup schedules and retention policies
3. **Service Checks**: Configure service availability monitoring
4. **Integrations**: Set up notification channels (Slack, PagerDuty)
5. **Log Alerts**: Configure alerts based on log patterns
6. **Dashboards**: Import and configure custom dashboards
7. **Alert Routes**: Configure routing rules for alerts

## Example Use Cases

### Configure Alerts for Multiple Clusters

```yaml
- name: Configure Alerts for Multiple Clusters
  hosts: localhost
  tasks:
    - name: Configure alerts for cluster 1
      include_role:
        name: axonops.axonops.alerts
      vars:
        org: mycompany
        cluster: cluster-1

    - name: Configure alerts for cluster 2
      include_role:
        name: axonops.axonops.alerts
      vars:
        org: mycompany
        cluster: cluster-2
```

## Notes

- **API Access**: Ensure you have proper API credentials configured for the AxonOps Server
- **Organization and Cluster**: The `org` and `cluster` variables must match existing entries in your AxonOps deployment
- **Idempotency**: The role is designed to be idempotent and can be run multiple times safely
- **Configuration Files**: Alert definitions can be customized by providing your own configuration files in the appropriate directories

## Additional Resources

For more information about AxonOps alerts and configuration, see:
- [ALERTS.md](../../ALERTS.md) in the repository root
- [AxonOps Documentation](https://docs.axonops.com/)

## License

See the main collection LICENSE file.

## Author

AxonOps Limited
