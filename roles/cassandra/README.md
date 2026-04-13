# AxonOps Cassandra Ansible Role

Installs and configures Apache Cassandra from the Apache tar distribution.

## Requirements

- Java must be installed before running this role (use `axonops.axonops.java`).

## Configuration

Key variables (see `defaults/main.yml` for the full list):

```yaml
cassandra_cluster_name: default
cassandra_dc: default
cassandra_rack: rack1
cassandra_max_heap_size: 1G
```

## Example Playbook

```yaml
- hosts: cassandra
  roles:
    - role: axonops.axonops.java
    - role: axonops.axonops.cassandra
      vars:
        cassandra_cluster_name: my-cluster
        cassandra_dc: dc1
```
