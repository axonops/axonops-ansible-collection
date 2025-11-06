# Configurations Role

## Overview

The `configurations` role configures alerts, integrations, and monitoring settings for your AxonOps deployment. This role manages metric alerts, backup configurations, service checks, integration with notification services (Slack, PagerDuty), log alerts, and custom dashboards.

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
    - role: axonops.axonops.configurations
```

### Using Environment Variables

```yaml
- name: Configure Alerts with Environment Variables
  hosts: localhost
  # Ensure AXONOPS_ORG and AXONOPS_CLUSTER are set in the environment

  roles:
    - role: axonops.axonops.configurations
```

### Configure Specific Configs Types

```yaml
- name: Configure Only Metric Alerts and Backups
  hosts: localhost
  vars:
    org: mycompany
    cluster: production-cluster

  roles:
    - role: axonops.axonops.configurations
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
    - role: axonops.axonops.configurations
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
    - role: axonops.axonops.configurations
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
    - role: axonops.axonops.configurations
```
## Details playbook

### Adaptive Repair Configuration

The Adaptive Repair feature can be configured by setting the `adaptive_repair` variable directly in the playbook, 
no need for files in the `config` directory. 

This allows you to enable or disable adaptive repair settings for your cluster.
#### List of Parameters
| Parameter             | Description                                                                      | Type    | Default |
|-----------------------|----------------------------------------------------------------------------------|---------|---------|
| `enabled`             | Enable or disable adaptive repair                                                | boolean | `true`  |
| `excludedtables`      | List of tables to exclude from adaptive repair.                                  | List    | `[]`    |
| `gc_grace`            | Set the GC grace period.                                                         | integer | `86400` |
| `maxsegmentspertable` | Set the maximum number of segments per table to repair in a single repair cycle. | integer | `0`     |
| `segmentretries`      | Set the number of retries for each segment in case of failure.                   | integer | `5`     |
| `segmenttargetsizemb` | Set the target size in MB for each segment repaired at time.                     | integer | `omit`  |
| `segmenttimeout`      | Set the timeout in seconds for each segment repair operation.                    | String  | `2h`    |
| `tableparallelism`    | Set the number of tables processed in parallel.                                  | integer | `10`    |

#### Enable Adaptive Repair

```yaml
- name: Enable Adaptive Repair
  hosts: localhost
  vars:
    org: mycompany
    cluster: production-cluster
    adaptive_repair:
      enabled: true

  roles:
    - role: axonops.axonops.configurations
```

#### Disable Adaptive Repair

```yaml
- name: Disable Adaptive Repair
  hosts: localhost
  vars:
    org: mycompany
    cluster: production-cluster
    adaptive_repair:
      enabled: false 
      
    roles:
      - role: axonops.axonops.configurations
```

#### Set GC Grace Threshold
Set the GC grace period. AxonOps will ignore tables that have a `gc_grace_seconds` value lower than the specified threshold. 
The default is `86400` seconds (1 day).

```yaml
- name: Set GC Grace Threshold for Adaptive Repair to 172800 seconds (2 days)
  hosts: localhost
  vars:
    org: mycompany
    cluster: production-cluster
    adaptive_repair:
      enabled: true
      gc_grace: 172800

  roles:
    - role: axonops.axonops.configurations
```

#### Set Table Parallelism

It is suggested to keep this value at least as the number of table in the cluster.
```yaml
- name: Set Table Parallelism for Adaptive Repair
  hosts: localhost
  vars:
    org: mycompany
    cluster: production-cluster
    adaptive_repair:
      enabled: true
      tableparallelism: 100

  roles:
    - role: axonops.axonops.configurations
```

#### Set Segment Retries

```yaml
- name: Set Segment Retries for Adaptive Repair
  hosts: localhost
  vars:
    org: mycompany
    cluster: production-cluster
    adaptive_repair:
        enabled: true
        segmentretries: 10

  roles:
    - role: axonops.axonops.configurations
```

#### Set Segment Target Size

Number from 16 to 10240
```yaml
- name: Set Segment Target Size for Adaptive Repair
  hosts: localhost
  vars:
    org: mycompany
    cluster: production-cluster
    adaptive_repair:
      enabled: true
      segmenttargetsizemb: 250
      
  roles:
    - role: axonops.axonops.configurations
```

#### Exclude Tables from Adaptive Repair
List of tables to exclude from adaptive repair. The accepted format is a list of strings in the form "keyspace.table".
To exclude an entire keyspace, use "keyspace.*".
The default is an empty list.

```yaml
- name: Exclude Tables from Adaptive Repair
  hosts: localhost
  vars:
    org: mycompany
    cluster: production-cluster
    adaptive_repair:
      enabled: true
      excludedtables:
      - "system.peers"
      - "system.local"

      
  roles:  
    - role: axonops.axonops.configurations
```

#### Set Maximum Segments per Table
Set the maximum number of segments per table to repair in a single repair cycle. 
Having too many segments in a table causes too many repair commands to be sent.

```yaml
- name: Set Maximum Segments per Table for Adaptive Repair
  hosts: localhost
  vars:
    org: mycompany
    cluster: production-cluster
    adaptive_repair:
      enabled: true
      maxsegmentspertable: 131072

  roles:
    - role: axonops.axonops.configurations
```

#### Set Segment Timeout
Set the timeout in seconds for each segment repair operation.
Integer number followed by one of "s, m, h, d, w, M, y"

```yaml
- name: Set Segment Timeout for Adaptive Repair
  hosts: localhost
  vars:
    org: mycompany
    cluster: production-cluster
    adaptive_repair:
      enabled: true
      segmenttimeout: "3h"

  roles:
    - role: axonops.axonops.configurations
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
