# Configurations Role

## Contents

- [Overview](#overview)
- [Requirements](#requirements)
- [Install the collection](#install-the-collection)
  - [Install from a release (recommended)](#install-from-a-release-recommended)
  - [Install directly from Git](#install-directly-from-git)
  - [Development mode (clone the repository)](#development-mode-clone-the-repository)
- [Authentication \& Settings](#authentication--settings)
  - [List of Variables](#list-of-variables)
- [Example Playbooks](#example-playbooks)
  - [Basic Alert Configuration](#basic-alert-configuration)
  - [Using Environment Variables](#using-environment-variables)
  - [Configure Specific Configs Types](#configure-specific-configs-types)
  - [Configure Slack Integration](#configure-slack-integration)
  - [Configure PagerDuty Integration](#configure-pagerduty-integration)
  - [Configure Microsoft Teams Integration](#configure-microsoft-teams-integration)
  - [Configure a Kafka Cluster](#configure-a-kafka-cluster)
  - [Full Alert Stack Configuration](#full-alert-stack-configuration)
- [Details playbook](#details-playbook)
  - [Adaptive Repair Configuration](#adaptive-repair-configuration)
    - [Enable Adaptive Repair](#enable-adaptive-repair)
    - [Disable Adaptive Repair](#disable-adaptive-repair)
    - [Set GC Grace Threshold](#set-gc-grace-threshold)
    - [Set Table Parallelism](#set-table-parallelism)
    - [Set Segment Retries](#set-segment-retries)
    - [Set Segment Target Size](#set-segment-target-size)
    - [Exclude Tables from Adaptive Repair](#exclude-tables-from-adaptive-repair)
    - [Set Maximum Segments per Table](#set-maximum-segments-per-table)
    - [Set Segment Timeout](#set-segment-timeout)
- [Kafka Cluster Support](#kafka-cluster-support)
- [Metric Alerts](#metric-alerts)
  - [List of parameters for metric_alert_rules](#list-of-parameters-for-metric_alert_rules)
  - [Check for DOWN nodes](#check-for-down-nodes)
  - [Check for High Disk Utilization](#check-for-high-disk-utilization)
- [Service Checks](#service-checks)
  - [List of parameters for axonops_shell_check](#list-of-parameters-for-axonops_shell_check)
  - [Dummy example of axonops_shell_check](#dummy-example-of-axonops_shell_check)
  - [Example: Debian/Ubuntu reboot check](#example-debianubuntu-reboot-check)
- [Microsoft Teams Integration](#microsoft-teams-integration)
- [Available Tags](#available-tags)
- [Tasks Overview](#tasks-overview)
- [Example Use Cases](#example-use-cases)
- [Notes](#notes)
- [Additional Resources](#additional-resources)
- [License](#license)
- [Author](#author)

## Overview

The `configurations` role configures alerts, integrations, and monitoring settings for your AxonOps deployment. This
role manages metric alerts, backup configurations, service checks, integration with notification services (Slack,
PagerDuty, Microsoft Teams), log alerts, and custom dashboards. The role supports both Apache Cassandra and Apache
Kafka clusters, controlled by the `cluster_type` variable.

## Requirements

- Ansible 2.9 or higher
- AxonOps Server installed and running
- AxonOps API access

## Install the collection

There are several ways to install the AxonOps Ansible Collection depending on your use case.

---

### Install from a release (recommended)

Download the latest release from GitHub and install it using `ansible-galaxy`:

```sh
ansible-galaxy collection install <downloaded_tar>
```

You may also use the following script to automatically download and install the latest version:

```sh
LATEST=$(curl -s https://api.github.com/repos/axonops/axonops-ansible-collection/releases/latest | jq -r '.assets[0].browser_download_url')
ansible-galaxy collection install $LATEST
```

**Note**: the tarball will be installed into the directory configured
in [COLLECTIONS_PATHS](https://docs.ansible.com/ansible/latest/reference_appendices/config.html#collections-paths).

**Verify installation:**
To verify the installation you can use the command:
`ansible-galaxy collection list | grep axonops`.
---

### Install directly from Git

To install the latest version from the repository:

```sh
ansible-galaxy collection install git+https://github.com/axonops/axonops-ansible-collection.git
```

To install from a specific branch:

```sh
ansible-galaxy collection install git+https://github.com/axonops/axonops-ansible-collection.git,main
```

**Verify installation:**
To verify the installation you can use the command:
`ansible-galaxy collection list | grep axonops`.


---

### Development mode (clone the repository)

For development or testing changes locally, you can clone the repository into a standard development directory (e.g.
`~/git`) and create a symbolic link so Ansible can detect it.

Clone the repository:

```shell
git clone https://github.com/axonops/axonops-ansible-collection.git ~/git/axonops-ansible-collection
```

Create the required Ansible collection path and link the repository:

```shell
mkdir -p ~/git/ansible_collections/axonops
ln -s ~/git/axonops-ansible-collection ~/git/ansible_collections/axonops/axonops
```

Ensure the parent directory is included in ANSIBLE_COLLECTIONS_PATHS:

```shell
export ANSIBLE_COLLECTIONS_PATHS=~/git:$ANSIBLE_COLLECTIONS_PATHS
```

To make this change persistent, add the above line to your shell configuration file (e.g. ~/.bashrc or ~/.zshrc).

**Verify installation:**
To verify the installation you can use the command:

```shell
ls -l ~/git/ansible_collections/axonops
```

---

## Authentication & Settings

The ansible role accepts configuration via both environment variables and Ansible variables.
The required variables are `org` and `cluster`, which can be set in either way.

### List of Variables

| Variable         | Description                                                                                                      | Environment Variable     | Example                 |
|------------------|------------------------------------------------------------------------------------------------------------------|--------------------------|-------------------------|
| `org`            | Organization name in AxonOps                                                                                     | `AXONOPS_ORG`            | `mycompany`             |
| `cluster`        | Cluster name to configure                                                                                        | `AXONOPS_CLUSTER`        | `production-cluster`    |
| `cluster_type`   | Type of cluster being configured (`cassandra`, `kafka` or `dse`). Default `cassandra`                            | `AXONOPS_CLUSTER_TYPE`   | `cassandra`             |
| `auth_token`     | API authentication token for AxonOps                                                                             | `AXONOPS_TOKEN`          | `aaaabbbbccccddddd`     |
| `username`       | Username for AxonOps API authentication (if LDAP authentication is enabled, self-hosted only)                    | `AXONOPS_USERNAME`       | `admin`                 |
| `password`       | Password for AxonOps API authentication (if LDAP authentication is enabled, self-hosted only)                    | `AXONOPS_PASSWORD`       | `I <3 AxonOps!`         |
| `enable_logging` | Optional flag to enable logging of API responses and errors (default: false)                                     | `AXONOPS_ENABLE_LOGGING` | `true`                  |
| `base_url`       | Base URL for the AxonOps (If you are not using AxonOps Cloud)                                                    | `AXONOPS_URL`            | `http://127.0.0.1:3000` |
| `validate_certs` | Optional flag to indicate if SSL certificates should be validated when connecting to the AxonOps (default: true) | `AXONOPS_VALIDATE_CERTS` | `true`                  |
| `use_saml`       | Set this to true if your AxonOps Cloud account has SAML authentication enabled (default: false)                  | `AXONOPS_USE_SAML`       | `false`                 |
| `api_token`      | API token for authentication. This is used when you have api token for AxonOps Self-Hosted.                      | `AXONOPS_API_TOKEN`      |                         |

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

### Configure Microsoft Teams Integration

```yaml
- name: Configure Alerts with Teams Integration
  hosts: localhost
  vars:
    org: mycompany
    cluster: production-cluster

  roles:
    - role: axonops.axonops.configurations
      tags:
        - teams
```

### Configure a Kafka Cluster

Set `cluster_type` to `kafka` to skip Cassandra-specific tasks and apply Kafka-appropriate alert rules.

```yaml
- name: Configure AxonOps Alerts for Kafka
  hosts: localhost
  vars:
    org: mycompany
    cluster: production-kafka
    cluster_type: kafka

  roles:
    - role: axonops.axonops.configurations
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

Set the GC grace period. AxonOps will ignore tables that have a `gc_grace_seconds` value lower than the specified
threshold.
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

### Kafka Cluster Support

When monitoring Apache Kafka clusters, set `cluster_type` to `kafka` either as a playbook variable or via the
`AXONOPS_CLUSTER_TYPE` environment variable. This prevents Cassandra-specific tasks (`adaptive_repair`,
`commitlogs_archive`, `human_readableid`) from running against a Kafka cluster.

Metric alert rules for Kafka use the same `axonops_alert_rules` variable and `metric_alert_rules.yml` file format as
Cassandra. Reference Kafka-specific dashboards and charts in your alert definitions.

Example Kafka alert rule:

```yaml
axonops_alert_rules:
  - name: Brokers Down
    dashboard: Kafka Overview
    chart: Brokers Online
    operator: '<'
    critical_value: 1
    warning_value: 2
    duration: 15m
    description: Detected Brokers Down

  - name: Offline Partitions
    dashboard: Kafka Replication
    chart: Offline Partitions
    operator: '>='
    critical_value: 10
    warning_value: 1
    duration: 5m
    description: Kafka partitions offline
```

A full set of example Kafka alert rules is available at
[examples/configurations/kafka/alert_rules.yml](../../examples/configurations/kafka/alert_rules.yml).

### Metric Alerts

Metric alerts can be configured by providing a YAML file called `metric_alert_rules.yml` in the directory
`config/[YOUR_ORG_NAME]` to make them available for all clusters in the organization, or in
`config/[YOUR_ORG_NAME]/[YOUR_CLUSTER_NAME]` to make them available for a specific cluster.

The file is optional. If the file is not provided, no metric alerts will be configured.
The format of the file is as follows:

```yaml
axonops_alert_rules:
  - name: name of the check
    dashboard: dashboard name
    chart: chart name
    operator: '>='
    critical_value: 2
    warning_value: 1
    duration: 15m
    description: my example metric alert
    enabled: true
```

The variable `axonops_alert_rules` is a list of metric alert definitions. The variable is optional.

#### list of parameters for metric_alert_rules

| Parameter        | Description                                                                                    | Type    | Default |
|------------------|------------------------------------------------------------------------------------------------|---------|---------|
| `name`           | Name of the alert                                                                              | String  |         |
| `description`    | Description of the alert                                                                       | String  |         |
| `chart`          | Name of the chart to monitor                                                                   | String  |         |
| `dashboard`      | Name of the dashboard containing the chart                                                     | String  |         |
| `operator`       | Comparison operator for the alert condition. Value accepted: '==', '>=', '>', '<=', '<', '!='. | String  |         |
| `critical_value` | Value to trigger a critical alert                                                              | Float   |         |
| `warning_value`  | Value to trigger a warning alert                                                               | Float   |         |
| `duration`       | Duration for which the condition must be met before triggering the alert                       | String  |         |
| `enabled`        | Whether the alert is enabled or not                                                            | Boolean | True    |

#### Check for DOWN nodes

This is an example of a metric alert that triggers a critical alert when the number of DOWN nodes per cluster
is greater than or equal to 2, and a warning alert when it is greater than or equal to 1, for a duration of 15 minutes.

```yaml
axonops_alert_rules:
  - name: DOWN count per node
    dashboard: Overview
    chart: Number of Endpoints Down Per Node Point Of View
    operator: '>='
    critical_value: 2
    warning_value: 1
    duration: 15m
    description: Detected DOWN nodes
```

#### Check for High Disk Utilization

This is an example of a metric alert that triggers a critical alert when the disk usage percentage for any mount point
is greater than or equal to 90%, and a warning alert when it is greater than or equal to 75%, for a duration of 12
hours.

```yaml
axonops_alert_rules:
  - name: Disk % Usage $mountpoint
    dashboard: System
    chart: Disk % Usage $mountpoint
    operator: '>='
    critical_value: 90
    warning_value: 75
    duration: 12h
    description: Detected High disk utilization
```

**Note:** More examples of metric checks can be found in the org level
[metric_alert_rules.yml](../../examples/configurations/cassandra/config/REPLACE_WITH_ORG_NAME/metric_alert_rules.yml) or
the cluster level
[metric_alert_rules.yml](../../examples/configurations/cassandra/config/REPLACE_WITH_ORG_NAME/REPLACE_WITH_CLUSTER_NAME/metric_alert_rules.yml)
example files. For Kafka-specific alert rules, see
[kafka/alert_rules.yml](../../examples/configurations/kafka/alert_rules.yml).

### Service Checks

Service checks can be configured by providing a YAML file called `service_checks.yml` in the directory
`config/[YOUR_ORG_NAME]`
to make them available for all clusters in the organization, or in `config/[YOUR_ORG_NAME]/[YOUR_CLUSTER_NAME]` to make
them available for a specific cluster.

The file is optional, if the file is not provided, no service checks will be configured.

The format of the file is as follows:

```yaml
axonops_shell_check: [ ]

axonops_tcp_check: [ ]
```

both `axonops_shell_check` and `axonops_tcp_checks` are optionals.

#### list of parameters for axonops_shell_check

| Parameter  | Description                           | Type    | Default     |
|------------|---------------------------------------|---------|-------------|
| `name`     | Name of the shell check               | String  |             |
| `present`  | Whether the check is present or not   | Boolean | True        |
| `interval` | How much ofthen the check need to run | String  |             |
| `timeout`  | Timeout for the check                 | String  |             |
| `shell`    | Shell used by the script              | String  | '/bin/bash' |
| `script`   | Script of the check                   | String  |             |

List of outcome codes for shell checks:

- `0`: OK
- `1`: WARNING
- `2`: CRITICAL

#### Dummy example of axonops_shell_check

This is example of a dummy shell check that always returns CRITICAL:

```yaml
axonops_shell_check:
  - name: "Dummy check"
    present: true
    interval: "5m"
    timeout: "10s"
    script: |
      #!/bin/bash
      echo "This is a dummy check"
      exit 2"
```

#### Example of a shell check to monitor if a Debian/Ubuntu host needs a reboot

This check looks for the presence of the file `/var/run/reboot-required`, which is created by the system when a reboot
is needed after package installations or updates.

```yaml
axonops_shell_check:
  - name: Debian / Ubuntu - Check host needs reboot
    interval: 12h
    present: true
    timeout: 1m
    script: |-
      set -euo pipefail

      if [ -f /var/run/reboot-required ]
      then
          echo `hostname` Reboot required
          exit 1
      else
          echo "Nothing to do"
      fi
```

**Note:** More examples of service checks can be found in the org level
[service_checks.yml](../../examples/configurations/cassandra/config/REPLACE_WITH_ORG_NAME/service_checks.yml) or the
cluster level
[service_checks.yml](../../examples/configurations/cassandra/config/REPLACE_WITH_ORG_NAME/REPLACE_WITH_CLUSTER_NAME/service_checks.yml)
example files.

### Microsoft Teams Integration

Teams integration can be configured by providing a YAML file called `teams_integrations.yml` in the directory
`config/[YOUR_ORG_NAME]` to apply to all clusters in the organization, or in
`config/[YOUR_ORG_NAME]/[YOUR_CLUSTER_NAME]` to apply to a specific cluster.

The file is optional. If the file is not provided, no Teams integrations will be configured.
The format of the file is as follows:

```yaml
axonops_teams_integrations:
  - name: my_teams_channel
    webhook_url: https://abcx360.webhook.office.com/webhookb2/YOUR_WEBHOOK_URL
    present: true
```

#### Parameters for axonops_teams_integrations

| Parameter     | Description                                               | Type    | Default |
|---------------|-----------------------------------------------------------|---------|---------|
| `name`        | Name of the integration (used to reference it in routing) | String  |         |
| `webhook_url` | Incoming webhook URL for the Teams channel                | String  |         |
| `present`     | Whether the integration should exist                      | Boolean | `true`  |

## Available Tags

The role supports granular control through the following tags:

| Tag                             | Description                             | Cluster Type   |
|---------------------------------|-----------------------------------------|----------------|
| `metrics`                       | Configure metric alerts                 | All            |
| `backups`                       | Configure backup settings               | All            |
| `service_checks`                | Configure service check alerts          | All            |
| `slack`                         | Configure Slack integration             | All            |
| `pagerduty_integration`         | Configure PagerDuty integration         | All            |
| `teams`                         | Configure Microsoft Teams integration   | All            |
| `adaptive_repair`               | Configure adaptive repair settings      | Cassandra only |
| `agent_disconnection_tolerance` | Configure agent disconnection tolerance | All            |
| `commitlogs_archive`            | Configure commit log archiving          | Cassandra only |
| `human_readableid`              | Configure human-readable IDs            | Cassandra only |
| `log_alerts`                    | Configure log-based alerts              | All            |
| `logcollector`                  | Configure log collector                 | All            |
| `dashboards`                    | Import custom dashboards                | All            |
| `routes`                        | Configure alert routing rules           | All            |

## Tasks Overview

The role performs the following tasks based on the enabled tags. Integrations are configured before metric alerts to
allow alert routing rules to reference integration names.

1. **Integrations**: Set up notification channels (Slack, PagerDuty, Microsoft Teams)
2. **Metrics Alerts**: Configure threshold-based alerts for cluster metrics
3. **Backup Configuration**: Set up backup schedules and retention policies
4. **Service Checks**: Configure service availability monitoring
5. **Adaptive Repair** (Cassandra only): Configure automated repair scheduling
6. **Agent Disconnection Tolerance**: Configure tolerance for agent disconnections
7. **Commit Log Archiving** (Cassandra only): Configure commit log archive settings
8. **Human-Readable IDs** (Cassandra only): Configure human-readable node identifiers
9. **Log Alerts**: Configure alerts based on log patterns
10. **Log Collector**: Configure log collection settings
11. **Dashboards**: Import and configure custom dashboards
12. **Alert Routes**: Configure routing rules for alerts

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
- **Configuration Files**: Alert definitions can be customized by providing your own configuration files in the
  appropriate directories

## Additional Resources

For more information about AxonOps alerts and configuration, see:

- [ALERTS.md](../../ALERTS.md) in the repository root
- [AxonOps Documentation](https://docs.axonops.com/)

## License

See the main collection LICENSE file.

## Author

AxonOps Limited
