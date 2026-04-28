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

## Kafka Alert Pack

A comprehensive set of default Kafka alert rules is provided in `examples/configurations/kafka/`. It covers:

- **JVM** — heap usage, GC pauses, thread deadlocks, file descriptor exhaustion
- **Broker cluster health** — active controller count, offline partitions, unclean leader elections (the three must-alert metrics)
- **Replication** — under-replicated partitions, ISR shrink rate, offline replicas, min-ISR violations
- **KRaft controller** — fenced brokers, metadata errors, broker metadata lag, snapshot age
- **Network & request processing** — idle percent thresholds, P99 produce/fetch latency, failed requests
- **Storage** — offline log directories, log flush latency, disk usage
- **Kafka Connect** — task/connector startup failures, offset commit failures, DLQ failures, authentication errors
- **Consumer lag** — consumer group lag max
- **Log-based alerts** — broker `server.log`, KRaft `controller.log`, GC log, Connect `connect.log`, authorizer log

### Quick Start

```bash
# 1. Copy the example config for your org and cluster
cp -r examples/configurations/kafka/config/REPLACE_WITH_ORG_NAME \
      examples/configurations/kafka/config/<your-org>

mv examples/configurations/kafka/config/<your-org>/REPLACE_WITH_CLUSTER_NAME \
   examples/configurations/kafka/config/<your-org>/<your-cluster>

# 2. Review and customise thresholds
#    Edit: examples/configurations/kafka/config/<your-org>/metric_alert_rules.yml
#    Edit: examples/configurations/kafka/config/<your-org>/log_alert_rules.yml

# 3. Deploy
cd examples/configurations/kafka
AXONOPS_TOKEN=<your-token> ansible-playbook kafka-alerts.yml \
  -e org=<your-org> -e cluster=<your-cluster>
```

Thresholds are starting points calibrated for typical production workloads. Re-evaluate per-cluster against observed steady-state behaviour, especially consumer lag (`Consumer Lag High`, default warning at 10,000 messages).
