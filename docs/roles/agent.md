# AxonOps Agent Role

## Overview

The `agent` role installs and configures the AxonOps Agent on Cassandra nodes. The AxonOps Agent collects metrics, logs, and diagnostic information from your Apache Cassandra or DataStax Enterprise (DSE) clusters and sends them to the AxonOps Server for monitoring and analysis.

## Requirements

- Ansible 2.9 or higher
- Target system running a supported Linux distribution (RHEL, CentOS, Ubuntu, Debian)
- Apache Cassandra or DataStax Enterprise installed (or install it using the `cassandra` role)
- Network connectivity to AxonOps Server (self-hosted or SaaS)

## Role Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `axon_agent_server_host` | Server name or IP where the AxonOps server is running | `agents.axonops.cloud` or `192.168.1.10` |
| `axon_agent_customer_name` | Organization name to identify your deployment | `mycompany` |

### Java Agent Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `axon_java_agent` | `axon-cassandra5.0-agent-jdk17` | Java agent version to install. Options: `axon-cassandra3.11-agent`, `axon-cassandra4.1-agent`, `axon-cassandra5.0-agent-jdk17`, `axon-dse6.0-agent`, `axon-dse6.7-agent`, `axon-dse5.1-agent`, or empty string to skip |
| `axon_agent_version` | `2.0.2` | Version of the AxonOps agent to install |
| `axon_java_agent_version` | `1.0.10` | Version of the Java agent to install |

### Network Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `axon_agent_server_port` | `443` (SaaS) or `1888` (self-hosted) | Port to connect to AxonOps Server |
| `axon_agent_host_name` | `{{ ansible_hostname }}` | Override the agent hostname if needed |

### TLS Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `axon_agent_tls_mode` | `disabled` | TLS mode: `disabled`, `TLS`, or `mTLS` |
| `axon_agent_tls_certfile` | - | Path to TLS certificate file (required for TLS/mTLS) |
| `axon_agent_tls_keyfile` | - | Path to TLS key file (required for TLS/mTLS) |
| `axon_agent_tls_cafile` | - | Path to CA certificate file (required for mTLS) |

### Cassandra Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `axon_agent_cassandra_config_directory` | - | Path to Cassandra configuration directory (e.g., `/opt/cassandra/conf`) to enable automatic agent configuration in `cassandra-env.sh` |
| `axon_agent_cassandra_config` | - | Configuration line to add to `cassandra-env.sh`. For Cassandra < 5: `JVM_OPTS="$JVM_OPTS -javaagent:/usr/share/axonops/axon-cassandra4.0-agent.jar=/etc/axonops/axon-agent.yml"`. For Cassandra >= 5: `. /usr/share/axonops/axonops-jvm.options` |

### Other Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `axon_agent_start_at_boot` | `true` | Enable the agent to start at boot |
| `axon_agent_state` | `present` | State of the agent: `present` or `absent` |
| `axon_agent_ntp_server` | `pool.ntp.org` | NTP server for time synchronization |

## Dependencies

None

## Example Playbooks

### Basic Agent Installation with SaaS

```yaml
- name: Install AxonOps Agent for SaaS
  hosts: cassandra
  become: true
  vars:
    axon_agent_customer_name: mycompany
    axon_java_agent: "axon-cassandra4.1-agent"

  roles:
    - role: axonops.axonops.agent
```

### Agent with Self-Hosted Server

```yaml
- name: Install AxonOps Agent with Self-Hosted Server
  hosts: cassandra
  become: true
  vars:
    axon_agent_server_host: "{{ groups['axon-server'] | first }}"
    axon_agent_customer_name: mycompany
    axon_java_agent: "axon-cassandra5.0-agent-jdk17"
    axon_agent_version: "2.0.2"
    axon_java_agent_version: "1.0.10"

  roles:
    - role: axonops.axonops.agent
      tags: agent
```

### Agent with TLS Enabled

```yaml
- name: Install AxonOps Agent with TLS
  hosts: cassandra
  become: true
  vars:
    axon_agent_server_host: axon-server.example.com
    axon_agent_customer_name: mycompany
    axon_java_agent: "axon-cassandra4.1-agent"
    axon_agent_tls_mode: "TLS"
    axon_agent_tls_certfile: /etc/axonops/certs/agent.crt
    axon_agent_tls_keyfile: /etc/axonops/certs/agent.key
    axon_agent_tls_cafile: /etc/axonops/certs/ca.crt

  roles:
    - role: axonops.axonops.agent
```

### Complete Stack: Java, Agent, and Cassandra

```yaml
- name: Deploy Complete Cassandra Stack with AxonOps
  hosts: cassandra
  become: true
  vars:
    axon_agent_server_host: "{{ groups['axon-server'] | first }}"
    axon_agent_customer_name: mycompany
    axon_java_agent: "axon-cassandra4.1-agent"
    java_pkg: java-11-openjdk-headless
    cassandra_dc: "DC1"
    cassandra_cluster_name: "production"
    cassandra_seeds: "{{ groups['cassandra'] | map('extract', hostvars, ['ansible_default_ipv4', 'address']) | list | first }}"

  roles:
    - role: axonops.axonops.java
      tags: java

    - role: axonops.axonops.agent
      tags: agent

    - role: axonops.axonops.cassandra
      tags: cassandra
```

### Agent with Automatic Cassandra Configuration

```yaml
- name: Install AxonOps Agent with Auto-Configuration
  hosts: cassandra
  become: true
  vars:
    axon_agent_server_host: "{{ groups['axon-server'] | first }}"
    axon_agent_customer_name: mycompany
    axon_java_agent: "axon-cassandra4.1-agent"
    # Automatically configure cassandra-env.sh
    axon_agent_cassandra_config_directory: /opt/cassandra/conf
    # For Cassandra < 5
    axon_agent_cassandra_config: 'JVM_OPTS="$JVM_OPTS -javaagent:/usr/share/axonops/axon-cassandra4.0-agent.jar=/etc/axonops/axon-agent.yml"'
    # For Cassandra >= 5, use this instead:
    # axon_agent_cassandra_config: '. /usr/share/axonops/axonops-jvm.options'

  roles:
    - role: axonops.axonops.agent
```

## Notes

- **Sudoers Configuration**: The role automatically configures sudo permissions for the axonops user to manage the Cassandra service
- **Automatic Cassandra Configuration**: You can optionally configure the role to automatically add the AxonOps agent configuration to Cassandra's `cassandra-env.sh` file by setting `axon_agent_cassandra_config_directory` and `axon_agent_cassandra_config`. Check the [AxonOps documentation](https://axonops.com/docs/get_started/agent_setup/) for the correct configuration line for your Cassandra version
- **Service Configuration**: By default, the role does not include the service-specific configuration in `axon-agent.yml` unless `axon_agent_include_service_config` is set to `true`
- **Repository Management**: The role supports public, beta, and dev repositories. Use `axon_agent_public_repository`, `axon_agent_beta_repository`, and `axon_agent_dev_repository` to control which repositories are enabled
- **Offline Installation**: For air-gapped environments, set `has_internet_access: false` and `axon_java_agent_force_offline_install: true`

## Tags

- `agent`: Apply all agent tasks
- `axonops-agent`: Alias for agent tag

## License

See the main collection LICENSE file.

## Author

AxonOps Limited
