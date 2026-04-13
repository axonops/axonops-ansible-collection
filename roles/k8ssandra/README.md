# AxonOps K8ssandra Ansible Role

Installs the K8ssandra operator via Helm and deploys a `K8ssandraCluster` custom resource with the AxonOps agent sidecar.

## Requirements

- A running Kubernetes cluster with `kubectl` and `helm` available on the control node.
- `kubernetes.core` Ansible collection.

## Example Playbook

```yaml
- hosts: localhost
  roles:
    - role: axonops.axonops.k8ssandra
```

See `defaults/main.yml` for the full list of configurable variables.
