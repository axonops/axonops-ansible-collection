# AxonOps CQL AI Ansible Role

This role installs and configures **CQL AI**, an AI-powered CQL shell for Apache Cassandra. It connects to a Cassandra cluster and provides an interactive query interface with AI assistance.

## Configuration

### Cassandra connection

```yaml
cqlai_host: "127.0.0.1"
cqlai_port: 9042
cqlai_keyspace: ""          # leave empty to connect without a default keyspace
# cqlai_username: "cassandra"
# cqlai_password: "cassandra"
```

### Behaviour

```yaml
cqlai_require_confirmation: true   # prompt before executing destructive statements
cqlai_consistency: "LOCAL_ONE"
cqlai_page_size: 100
cqlai_history_file: "~/.cqlai/history"
cqlai_ai_history_file: "~/.cqlai/ai_history"
```

### TLS / SSL

SSL is enabled by default. Set `cqlai_ssl_enabled` to `false` if your cluster does not use TLS.

```yaml
cqlai_ssl_enabled: true
cqlai_ssl_cert_path: "/opt/ssl/{{ inventory_hostname }}.crt"
cqlai_ssl_key_path: "/opt/ssl/{{ inventory_hostname }}.key"
cqlai_ssl_ca_path: ""
cqlai_ssl_host_verification: false
cqlai_ssl_insecure_skip_verify: true
```

### AI provider

```yaml
cqlai_ai_provider: "openai"
cqlai_ai_openai_api_key: ""   # set your OpenAI API key here (use Ansible Vault)
```

### Package version

```yaml
cqlai_version: latest   # pin to a specific version if required
```

## Running

```yaml
- hosts: cassandra
  become: true
  roles:
    - role: axonops.axonops.cqlai
      vars:
        cqlai_host: "{{ ansible_default_ipv4.address }}"
        cqlai_ai_provider: "openai"
        cqlai_ai_openai_api_key: "{{ vault_openai_api_key }}"
```
