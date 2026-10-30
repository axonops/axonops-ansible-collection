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
    org: mycompany            # required (or AXONOPS_ORG)
    cluster: my-cluster       # required (or AXONOPS_CLUSTER)
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

A comprehensive set of default Kafka alert rules is provided in `examples/configurations/kafka/`. The pack is split into two files per scope level:

**Metric alert rules** (`metric_alert_rules.yml`) — 31 rules covering:

- **Broker cluster health** — active controller count, offline partitions, unclean leader elections (the minimum three alerts every cluster must have)
- **Replication** — under-replicated partitions, ISR shrink rate, under-min-ISR partitions
- **KRaft controller** — metadata error rate, raft commit latency, preferred replica imbalance
- **Network & request processing** — network and request handler idle percent, request queue depth, request total time
- **Storage** — disk usage percentage
- **Kafka Connect** — connector/task failures, task running ratio, offset commit success rate, DLQ produce failures, record errors and skips, authentication failures, rebalance failures
- **Consumer groups** — consumer group lag
- **System** — CPU usage, disk usage, I/O wait, memory usage, authentication failure rate

**Log-based alert rules** (`log_alert_rules.yml`) — 31 rules covering:

- **Broker startup and availability** — startup failure, OOM, FATAL errors, storage exceptions, data directory failures, log flush I/O errors, disk lock errors (`server.log`)
- **Replication and partition health** — under-replicated partitions, ISR shrink events (`server.log`, `state-change.log`)
- **Security and authentication** — authorisation failures (`kafka-authorizer.log`), authentication failures (`server.log`)
- **JVM GC** — full GC events, long GC pauses, G1GC mark abort, OOM (`kafkaServer-gc.log`)
- **KRaft controller** — no-quorum leader, FATAL and ERROR conditions, OOM, quorum instability, metadata load errors (`controller.log`)
- **Kafka Connect** — worker FATAL errors, startup failures, task FAILED transitions, offset commit failures, deserialisation errors, REST API unreachable, broker connection loss (`connect.log`)

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

## Adaptive Repair

> **Requires axon-server ≥ 2.0.41.**

Configure Adaptive Repair via the `adaptive_repair` variable:

```yaml
adaptive_repair:
  enabled: true
  gc_grace: 86400
  maxconcurrentsegments: -1     # -1 = auto-calculate from cluster topology
  repairaheadofschedule: false  # enable to run repairs faster than strictly needed
  segmenttargetsizemb: 1024
  segmentretries: 3
  segmenttimeout: 2h
  maxsegmentspertable: 0
  filter_twcs: true
  excludedtables: []
```

| Variable | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `true` | Enable or disable Adaptive Repair |
| `gc_grace` | int | `86400` | Skip tables whose `gc_grace_seconds` is below this value |
| `maxconcurrentsegments` | int | `-1` | Max repair segments in flight across the cluster. `-1` = auto-calculated from cluster topology |
| `repairaheadofschedule` | bool | `false` | Allow tables ahead of schedule to use spare slots when cluster health is green |
| `segmenttargetsizemb` | int | `1024` | Target segment size in MB |
| `segmentretries` | int | `3` | Max retries before failing a segment |
| `segmenttimeout` | str | `2h` | Timeout per segment |
| `maxsegmentspertable` | int | `0` | Max segments per table (0 = no limit) |
| `filter_twcs` | bool | `true` | Skip TimeWindowCompactionStrategy tables |
| `excludedtables` | list | `[]` | Tables to exclude from repair |
