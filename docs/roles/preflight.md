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
| `preflight_check_memory` | `true` | Report system memory (informational, never fails) |
| `preflight_check_ntp` | `true` | Check that `chronyd` or `ntpd` is installed |
| `preflight_check_os` | `true` | Check if operating system is supported |
| `preflight_check_cassandra_data_directory` | `true` | Check that `cassandra_data_directory` is not on NFS/CIFS/GlusterFS |
| `preflight_check_swap` | `true` | Fail if swap is enabled |

## Dependencies

None

## What the Role Checks

### Memory Check
- Runs `free -m` and reads total memory
- Never fails the play: it only prints a debug message and does not enforce a minimum (8 GB is the recommended minimum for Cassandra)

### NTP Check
- Fails unless `chronyd` or `ntpd` is installed (`chronyd -v` or `ntpd -v` succeeds)
- Checks installation only, not that the service is running or synchronised

### OS Check
- Fails unless `ansible_distribution` is one of Ubuntu, Debian, CentOS, RedHat, Rocky or Amazon
- Does not check the OS version

### Cassandra Data Directory Check
- Runs only when `cassandra_data_directory` is set and not empty
- Fails if the directory is on `nfs`, `cifs` or `glusterfs`
- Does not check free space or create the directory

### Swap Check
- Fails if `swapon --show` returns any output (swap enabled)
- Does not check `vm.swappiness`

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
    cassandra_version: 5.0.9
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
    cassandra_version: 5.0.9
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

### Memory Check Output

**Problem**: The memory check prints a message (it does not fail) when the host has insufficient memory for Cassandra.

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

### Swap Check Failure

**Problem**: Swap is enabled, which degrades Cassandra performance. The check fails the play.

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

**Problem**: `cassandra_data_directory` is on NFS, CIFS or GlusterFS.

**Solution**:
- Point `cassandra_data_directory` at local or block storage

## Best Practices

1. **Always Run Preflight**: Include preflight checks in your deployment playbooks to catch issues early

2. **Address All Warnings**: Don't ignore preflight warnings, as they can lead to performance issues or failures

3. **Use in CI/CD**: Incorporate preflight checks in your continuous deployment pipelines

4. **Document Exceptions**: If you disable certain checks, document why in your playbook

5. **Verify in Production**: Run preflight checks on production systems during maintenance windows to ensure continued compliance

## Tags

The role defines no tags of its own. Tag the role in your play (for example `tags: preflight`) to select or skip it.

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

- **Blocking**: The NTP, OS, swap and data directory checks fail the play when they do not pass. The memory check is informational only
- **Best Effort**: Some checks may not apply to all environments (e.g., containerized deployments)
- **Customization**: You can extend this role with your own checks by adding tasks
- **Read-only**: The role makes no changes to the system
- **Early Detection**: Running preflight checks before installation saves time by catching issues early

## License

See the main collection LICENSE file.

## Author

AxonOps Limited
