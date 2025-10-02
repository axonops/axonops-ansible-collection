# Preflight Role

## Overview

The `preflight` role performs pre-installation checks on target systems before deploying Cassandra or other AxonOps components. These checks help ensure that your systems meet the necessary requirements for a successful deployment.

## Requirements

- Ansible 2.9 or higher
- Target system running a supported Linux distribution

## Role Variables

All preflight checks are enabled by default and can be individually disabled by setting the corresponding variable to `false`.

| Variable | Default | Description |
|----------|---------|-------------|
| `preflight_check_memory` | `true` | Check if system has sufficient memory |
| `preflight_check_ntp` | `true` | Check if NTP/time synchronization is configured |
| `preflight_check_os` | `true` | Check if operating system is supported |
| `preflight_check_cassandra_data_directory` | `true` | Check if Cassandra data directories have sufficient space |
| `preflight_check_swap` | `true` | Check swap configuration (swap should be disabled for Cassandra) |

## Dependencies

None

## What the Role Checks

### Memory Check
- Verifies the system has sufficient RAM for running Cassandra
- Ensures available memory meets minimum requirements

### NTP Check
- Verifies time synchronization is configured and running
- Checks for `chronyd`, `ntpd`, or `systemd-timesyncd`
- Ensures clocks are synchronized across cluster nodes

### OS Check
- Verifies the operating system is supported
- Checks OS version compatibility
- Validates distribution-specific requirements

### Cassandra Data Directory Check
- Verifies data directories exist or can be created
- Checks available disk space in data directories
- Ensures sufficient storage for Cassandra operations

### Swap Check
- Verifies swap is disabled or minimal
- Warns if swap is enabled (swap can degrade Cassandra performance)
- Checks `vm.swappiness` kernel parameter

## Example Playbooks

### Run All Preflight Checks

```yaml
- name: Run Preflight Checks
  hosts: cassandra
  become: true

  roles:
    - role: axonops.axonops.preflight
```

### Run Specific Preflight Checks

```yaml
- name: Run Memory and NTP Checks Only
  hosts: cassandra
  become: true
  vars:
    preflight_check_memory: true
    preflight_check_ntp: true
    preflight_check_os: false
    preflight_check_cassandra_data_directory: false
    preflight_check_swap: false

  roles:
    - role: axonops.axonops.preflight
```

### Disable Swap Check

```yaml
- name: Run Preflight Without Swap Check
  hosts: cassandra
  become: true
  vars:
    preflight_check_swap: false

  roles:
    - role: axonops.axonops.preflight
```

### Preflight Before Cassandra Installation

```yaml
- name: Deploy Cassandra with Preflight Checks
  hosts: cassandra
  become: true
  vars:
    cassandra_version: 5.0.5
    cassandra_cluster_name: production
    java_pkg: java-17-openjdk-headless

  roles:
    - role: axonops.axonops.preflight
      tags: preflight

    - role: axonops.axonops.java
      tags: java

    - role: axonops.axonops.cassandra
      tags: cassandra
```

### Complete Stack with Preflight

```yaml
- name: Deploy Complete Stack with Preflight Checks
  hosts: cassandra
  become: true
  vars:
    # Preflight configuration
    preflight_check_memory: true
    preflight_check_ntp: true
    preflight_check_os: true
    preflight_check_cassandra_data_directory: true
    preflight_check_swap: true

    # Cassandra configuration
    cassandra_version: 5.0.5
    cassandra_cluster_name: production
    cassandra_dc: DC1
    java_pkg: java-17-openjdk-headless

    # AxonOps Agent configuration
    axon_agent_server_host: "{{ groups['axon-server'] | first }}"
    axon_java_agent: "axon-cassandra5.0-agent-jdk17"

  roles:
    - role: axonops.axonops.preflight
      tags: preflight

    - role: axonops.axonops.java
      tags: java

    - role: axonops.axonops.agent
      tags: agent

    - role: axonops.axonops.cassandra
      tags: cassandra
```

### Skip Preflight Checks

If you need to skip preflight checks entirely, you can use tags:

```yaml
- name: Deploy Without Preflight
  hosts: cassandra
  become: true

  roles:
    - role: axonops.axonops.preflight
      tags: preflight  # Skip by not including this tag

    - role: axonops.axonops.cassandra
      tags: cassandra
```

Then run with:
```bash
ansible-playbook playbook.yml --skip-tags preflight
```

## Common Preflight Failures and Solutions

### Memory Check Failure

**Problem**: System has insufficient memory for Cassandra.

**Solution**:
- Increase system RAM
- Adjust Cassandra heap size to match available memory
- Consider using a larger instance type

### NTP Check Failure

**Problem**: Time synchronization is not configured or not running.

**Solution**:
```yaml
- name: Install and Configure Chrony
  ansible.builtin.package:
    name: chrony
    state: present

- name: Start and Enable Chrony
  ansible.builtin.service:
    name: chronyd
    state: started
    enabled: true
```

### Swap Check Warning

**Problem**: Swap is enabled and may impact Cassandra performance.

**Solution**:
```yaml
- name: Disable Swap
  ansible.builtin.command: swapoff -a

- name: Remove Swap from fstab
  ansible.builtin.lineinfile:
    path: /etc/fstab
    regexp: '.*swap.*'
    state: absent

- name: Set vm.swappiness to 0
  ansible.posix.sysctl:
    name: vm.swappiness
    value: '0'
    state: present
    reload: true
```

### Data Directory Check Failure

**Problem**: Insufficient disk space or directory doesn't exist.

**Solution**:
- Add more storage to the system
- Mount additional volumes for Cassandra data directories
- Clean up existing data if this is a test environment

## Best Practices

1. **Always Run Preflight**: Include preflight checks in your deployment playbooks to catch issues early

2. **Address All Warnings**: Don't ignore preflight warnings, as they can lead to performance issues or failures

3. **Use in CI/CD**: Incorporate preflight checks in your continuous deployment pipelines

4. **Document Exceptions**: If you disable certain checks, document why in your playbook

5. **Verify in Production**: Run preflight checks on production systems during maintenance windows to ensure continued compliance

## Tags

- `preflight`: Apply all preflight check tasks

## Integration Example

### Pre-flight with Conditional Installation

```yaml
- name: Preflight and Conditional Cassandra Install
  hosts: cassandra
  become: true
  vars:
    run_preflight: true
    install_cassandra: true

  roles:
    - role: axonops.axonops.preflight
      when: run_preflight | default(false)
      tags: preflight

    - role: axonops.axonops.cassandra
      when: install_cassandra | default(false)
      tags: cassandra
```

## Notes

- **Non-blocking**: By default, preflight checks warn about issues but don't necessarily block installation
- **Best Effort**: Some checks may not apply to all environments (e.g., containerized deployments)
- **Customization**: You can extend this role with your own checks by adding tasks
- **Idempotent**: The role is safe to run multiple times and won't make changes to the system
- **Early Detection**: Running preflight checks before installation saves time by catching issues early

## License

See the main collection LICENSE file.

## Author

AxonOps Limited
