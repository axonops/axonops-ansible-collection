# AxonOps Server Ansible Role

Installs and configures the AxonOps server (`axon-server`).

## Configuration

```yaml
axon_server_state: present   # present or absent
axon_server_version: latest  # version to install
axon_server_hum: false       # enable human-readable metrics
```

## Example Playbook

```yaml
- hosts: axonops_server
  roles:
    - role: axonops.axonops.server
      vars:
        axon_server_version: latest
```
