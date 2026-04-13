# AxonOps Java Ansible Role

Installs Java (OpenJDK or Zulu) on the target hosts.

## Configuration

```yaml
# Use Zulu Java instead of OpenJDK (Debian-based systems only)
java_use_zulu: false

# Install EPEL repository on RHEL-based systems before installing Java
java_install_epel: false
```

## Example Playbook

```yaml
- hosts: cassandra
  roles:
    - role: axonops.axonops.java
```
