# AxonOps Java Ansible Role

Installs Java (OpenJDK or Zulu) on the target hosts.

## Configuration

```yaml
# Use Zulu Java instead of OpenJDK (RedHat and Debian families).
# Selected automatically on RHEL-family 10+ and Debian 13+.
java_use_zulu: false

# Java package to install (OpenJDK). Derived from cassandra_version when unset:
# Java 17 for 5.x, Java 8 for 3.11.x, otherwise Java 11.
# java_pkg: java-17-openjdk-headless

# Declared but not used by any task; the role does not install EPEL
java_install_epel: false
```

## Example Playbook

```yaml
- hosts: cassandra
  roles:
    - role: axonops.axonops.java
```
