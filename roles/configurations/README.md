# AxonOps Configurations Ansible Role

Manages AxonOps configuration resources — alert rules, log alerts, dashboards, integrations, adaptive repair, and more — via the AxonOps API.

## Requirements

A running AxonOps server and a valid API token (`AXONOPS_TOKEN`) or username/password.

## Authentication

```yaml
# Token-based (recommended)
AXONOPS_TOKEN: <your-token>

# Or username/password
AXONOPS_USERNAME: admin
AXONOPS_PASSWORD: secret
```

## Example Playbook

```yaml
- hosts: localhost
  vars:
    axonops_alert_rules:
      - name: High CPU
        dashboard: System
        chart: CPU usage per host
        operator: '>='
        critical_value: 99
        warning_value: 90
        duration: 1h
        description: High CPU usage detected
  roles:
    - role: axonops.axonops.configurations
```
