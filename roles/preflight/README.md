# AxonOps Preflight Ansible Role

Runs pre-flight checks on target hosts before deploying Cassandra or other AxonOps components.

## Checks

| Variable | Default | Description |
|---|---|---|
| `preflight_check_memory` | `true` | Report system memory (informational, never fails) |
| `preflight_check_ntp` | `true` | Verify `chronyd` or `ntpd` is installed |
| `preflight_check_os` | `true` | Verify OS is supported |
| `preflight_check_cassandra_data_directory` | `true` | Verify `cassandra_data_directory` is not on NFS/CIFS/GlusterFS |
| `preflight_check_swap` | `true` | Verify swap is disabled |

## Example Playbook

```yaml
- hosts: cassandra
  roles:
    - role: axonops.axonops.preflight
```
