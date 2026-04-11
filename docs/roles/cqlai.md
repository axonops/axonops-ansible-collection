# CQL AI Role

## Overview

The `cqlai` role installs and configures CQL AI, an AI-powered CQL shell for Apache Cassandra. CQL AI connects to a Cassandra cluster and provides an interactive query interface with AI assistance, including natural-language query generation and confirmation prompts for destructive statements.

## Requirements

- Ansible 2.10 or higher
- Target system running a supported Linux distribution (RHEL, CentOS, Ubuntu, Debian)
- Network connectivity to the target Cassandra cluster
- An OpenAI API key (or compatible AI provider key) stored in Ansible Vault

## Role Variables

### Package Version

| Variable | Default | Description |
|----------|---------|-------------|
| `cqlai_version` | `latest` | CQL AI package version to install. Pin to a specific version in production to prevent uncontrolled upgrades |

### Cassandra Connection

| Variable | Default | Description |
|----------|---------|-------------|
| `cqlai_host` | `127.0.0.1` | Hostname or IP address of the Cassandra node to connect to |
| `cqlai_port` | `9042` | CQL native transport port |
| `cqlai_keyspace` | `""` | Default keyspace. Leave empty to connect without selecting a keyspace |
| `cqlai_username` | — | Cassandra username. Omit if authentication is not enabled |
| `cqlai_password` | — | Cassandra password. MUST be stored in Ansible Vault |

### Behaviour

| Variable | Default | Description |
|----------|---------|-------------|
| `cqlai_require_confirmation` | `true` | Prompt for confirmation before executing destructive statements (DROP, TRUNCATE). SHOULD remain `true` in production |
| `cqlai_consistency` | `LOCAL_ONE` | Default CQL consistency level |
| `cqlai_page_size` | `100` | Number of rows returned per page |
| `cqlai_history_file` | `~/.cqlai/history` | Path to the CQL command history file |
| `cqlai_ai_history_file` | `~/.cqlai/ai_history` | Path to the AI interaction history file |

### TLS / SSL

SSL is enabled by default. Set `cqlai_ssl_enabled` to `false` only if the target Cassandra cluster does not use TLS.

| Variable | Default | Description |
|----------|---------|-------------|
| `cqlai_ssl_enabled` | `true` | Enable TLS for the Cassandra connection |
| `cqlai_ssl_cert_path` | `/opt/ssl/{{ inventory_hostname }}.crt` | Path to the client TLS certificate on the target host |
| `cqlai_ssl_key_path` | `/opt/ssl/{{ inventory_hostname }}.key` | Path to the client TLS private key on the target host |
| `cqlai_ssl_ca_path` | `""` | Path to the CA certificate. Leave empty to use system trust store |
| `cqlai_ssl_host_verification` | `false` | Verify the Cassandra server hostname against its TLS certificate |
| `cqlai_ssl_insecure_skip_verify` | `true` | Skip TLS certificate verification. SHOULD be set to `false` in production |

> **Warning:** `cqlai_ssl_insecure_skip_verify: true` disables certificate validation and exposes the connection to man-in-the-middle attacks. Set it to `false` and supply a valid CA certificate via `cqlai_ssl_ca_path` for production deployments.

### AI Provider

| Variable | Default | Description |
|----------|---------|-------------|
| `cqlai_ai_provider` | `openai` | AI provider to use for query assistance |
| `cqlai_ai_openai_api_key` | `""` | API key for the AI provider. MUST be set; MUST be stored in Ansible Vault — never in plaintext |

## Dependencies

None.

## Example Playbooks

### Basic Installation

Install CQL AI on Cassandra nodes and connect to the local Cassandra instance:

```yaml
- name: Install CQL AI on Cassandra nodes
  hosts: cassandra
  become: true

  roles:
    - role: axonops.axonops.cqlai
      vars:
        cqlai_host: "{{ ansible_default_ipv4.address }}"
        cqlai_ai_provider: "openai"
        cqlai_ai_openai_api_key: "{{ vault_openai_api_key }}"
```

### Production Installation with TLS Verification

Enables certificate verification and pins the package version:

```yaml
- name: Install CQL AI (production)
  hosts: cassandra
  become: true

  roles:
    - role: axonops.axonops.cqlai
      vars:
        cqlai_version: "1.2.0"
        cqlai_host: "{{ ansible_default_ipv4.address }}"
        cqlai_username: "cqlai_user"
        cqlai_password: "{{ vault_cassandra_cqlai_password }}"
        cqlai_ssl_enabled: true
        cqlai_ssl_cert_path: "/etc/cassandra/tls/client.crt"
        cqlai_ssl_key_path: "/etc/cassandra/tls/client.key"
        cqlai_ssl_ca_path: "/etc/cassandra/tls/ca.crt"
        cqlai_ssl_host_verification: true
        cqlai_ssl_insecure_skip_verify: false
        cqlai_ai_provider: "openai"
        cqlai_ai_openai_api_key: "{{ vault_openai_api_key }}"
        cqlai_require_confirmation: true
        cqlai_consistency: "LOCAL_QUORUM"
```

### Without TLS

For Cassandra clusters that do not use TLS:

```yaml
- name: Install CQL AI (no TLS)
  hosts: cassandra
  become: true

  roles:
    - role: axonops.axonops.cqlai
      vars:
        cqlai_host: "{{ ansible_default_ipv4.address }}"
        cqlai_ssl_enabled: false
        cqlai_ai_provider: "openai"
        cqlai_ai_openai_api_key: "{{ vault_openai_api_key }}"
```

## Notes

- **API key security**: `cqlai_ai_openai_api_key` MUST be provided via Ansible Vault or an equivalent secrets manager. Storing it in plaintext in a playbook or inventory file exposes it to anyone with repository access.
- **Confirmation prompts**: `cqlai_require_confirmation` defaults to `true`. Disabling it allows destructive statements to execute without prompting — only do this in non-production environments where the risk is understood.
- **Package version**: The default `cqlai_version: latest` installs the newest available package on each run. Pin to a specific version in production to ensure consistent behaviour across nodes and prevent unintended upgrades.
- **Repository configuration**: The role uses the AxonOps package repository. The `axon_agent_public_repository`, `axon_agent_beta_repository`, and `axon_agent_dev_repository` variables control which repository is enabled, defaulting to the public release repository.

## License

See the main collection LICENSE file.

## Author

AxonOps Limited
