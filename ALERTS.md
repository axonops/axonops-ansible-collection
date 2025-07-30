# AxonOps Alerts Role

The `alerts` role in the AxonOps Ansible Collection automates the configuration and management of alerting, monitoring, and notification integrations for your AxonOps-managed clusters. It supports metric and log-based alerts, backup monitoring, service checks, and integrations with external services like Slack and PagerDuty.

## Features

- **Metric Alerts**: Define and manage metric-based alert rules.
- **Log Alerts**: Configure log-based alerting for cluster events.
- **Alert Routing**: Set up routing rules to direct alerts to specific integrations.
- **Service Checks**: Run shell and TCP checks for service health.
- **Backup Monitoring**: Manage backup schedules and retention.
- **Integrations**: Slack, PagerDuty, and more.
- **Dashboard Templates**: Manage dashboard templates for visualization.
- **Advanced**: Adaptive repair, agent disconnection tolerance, log collection, and more.

## Requirements

- Ansible 2.9+
- AxonOps Ansible Collection installed (`axonops.axonops`)
- The following variables must be set (either as environment variables or in your playbook/inventory):
  - `org`: Your AxonOps organization name (or set `AXONOPS_ORG` env var)
  - `cluster`: The cluster name (or set `AXONOPS_CLUSTER` env var)

## Environment config

Before you can run the playbook, you'll need to define the following variables. You can do the either as *environment variables* or *Ansible Variables*. If you use ansible variables, it's stronglly advised to ue Ansible Vault or similar.

| Variable    | Environment Variable(s)           | Description |
|-------------|-----------------------------------|-------------|
| org         | AXONOPS_ORG                       | Organization name in AxonOps |
| cluster     | AXONOPS_CLUSTER                   | Cluster name to configure alerts for |
| auth_token  | AXONOPS_TOKEN or AXONOPS_API_TOKEN| API authentication token for AxonOps |
| username    | AXONOPS_USERNAME                  | Username for AxonOps API authentication (if not using token) |
| password    | AXONOPS_PASSWORD                  | Password for AxonOps API authentication (if not using token) |

## Directory Structure

The `alerts` role can load the alerts configuration from a custom `config` directory as explained below or you can define the alerts
as part of your regulard `group_vars` or inventory configuration.

Configuration files are expected under a `config/` directory, typically organized as:

```
config/
  <ORG_NAME>/
    metric_alert_rules.yml
    log_alert_rules.yml
    alert_routes.yml
    service_checks.yml
    slack_integrations.yml
    pagerduty_integrations.yml
    dashboards.yml
    <CLUSTER_NAME>/
      metric_alert_rules.yml
      log_alert_rules.yml
      alert_routes.yml
      backups.yml
      commitlog_archive.yml
      service_checks.yml
      ...
```

## Example Playbook

The example playbook does not use the `config/` directory but it will read it if present.

```yaml
- name: Configure AxonOps Alerts
  hosts: all
  vars:
    org: "myorg"
    cluster: "mycluster"
    enable_logging: true
    axonops_alert_rules:
      - name: CPU usage per host
        dashboard: System
        chart: CPU usage per host
        operator: '>='
        critical_value: 99
        warning_value: 90
        duration: 1h
        description: Detected High CPU usage
    axonops_log_alert_rule:
      - name: Node Down
        warning_value: 1
        critical_value: 5
        duration: 5m
        content: "is now DOWN"
        description: Detected node down
        source: "/var/log/cassandra/system.log"
    axonops_slack_integrations:
      - name: example_slack
        webhook_url: https://hooks.slack.com/services/ADD/ME/HERE
    axonops_alert_routes:
      - integration_name: example_slack
        integration_type: slack
        type: global
        severity: error
        enable_override: false

  roles:
    - role: axonops.axonops.alerts
```

## Supported Variables

- `axonops_alert_rules`: List of metric alert rules.
- `axonops_log_alert_rule`: List of log alert rules.
- `axonops_shell_check`: List of shell service checks.
- `axonops_tcp_check`: List of TCP service checks.
- `axonops_slack_integrations`: List of Slack integration configs.
- `axonops_pagerduty_integrations`: List of PagerDuty integration configs.
- `axonops_alert_routes`: List of alert routing rules.
- `axonops_dashboard_templates`: List of dashboard templates.
- `axonops_backups`: List of backup configurations.
- `axonops_commitlog_archive`: List of commitlog archive configs.
- `adaptive_repair`, `agent_disconnection_tolerance`, `human_readableid`, `logcollectors`: Advanced/optional features.

## Tags

You can use tags to run only specific parts of the role, e.g.:
- `metrics`
- `logs`
- `backups`
- `service_checks`
- `slack`
- `pagerduty_integration`
- `routes`
- `dashboards`
- `adaptive_repair`
- `commitlogs_archive`
- `logcollector`
- `human_readableid`
