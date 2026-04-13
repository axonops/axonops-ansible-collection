# AxonOps Strimzi Ansible Role

Installs the Strimzi Kafka operator via Helm and deploys `KafkaNodePool` and `Kafka` custom resources in KRaft mode.

## Requirements

- A running Kubernetes cluster with `kubectl` and `helm` available on the control node.
- `kubernetes.core` Ansible collection.
- Strimzi 0.51 or later (KRaft mode only — ZooKeeper not supported).

## Example Playbook

```yaml
- hosts: localhost
  roles:
    - role: axonops.axonops.strimzi
```

See `defaults/main.yml` for the full list of configurable variables.
