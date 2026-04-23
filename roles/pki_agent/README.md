# pki_agent Role

Installs and configures [OpenBao Agent](https://openbao.org/docs/agent-and-proxy/agent) for automated PKI certificate lifecycle management. The agent authenticates to an OpenBao server, issues X.509 certificates via the PKI secrets engine, and writes them to disk. It monitors certificate expiry and rotates them automatically before the TTL expires — no cron jobs, no manual renewals.

This role is **OpenBao-only**. HashiCorp Vault is not supported.

## Requirements

- **Ansible** 2.10 or higher
- **OpenBao server** reachable from each target host, with:
  - The PKI secrets engine mounted and configured
  - An AppRole or token credential with `create`/`update` capability on the relevant `pki/issue/*` or `pki/sign/*` paths
- **Target OS**: systemd-based Linux — see supported platforms below

### Supported Platforms

| Family | Versions |
|--------|----------|
| RHEL / AlmaLinux / Rocky Linux | 8, 9, 10 |
| Fedora | all |
| Debian | all |
| Ubuntu | all |

## Role Variables

### Installation

| Variable | Default | Description |
|----------|---------|-------------|
| `pki_agent_version` | `""` | OpenBao package version to install. The empty string installs the latest available version from the repository. Pinning a version is RECOMMENDED for production — example: `"2.1.0"` |
| `pki_agent_install_method` | `"pkg"` | Install method: `pkg` (OS package manager, adds the official OpenBao repository) or `binary` (downloads a release zip directly from GitHub). See [Binary Install](#binary-install) |

### OpenBao Server Connection

| Variable | Default | Description |
|----------|---------|-------------|
| `pki_agent_addr` | `""` | **Required.** URL of the OpenBao server — example: `"https://openbao.internal.example.com:8200"`. The role fails immediately if this is empty |
| `pki_agent_namespace` | `""` | OpenBao namespace. Omitted from the configuration when empty |

### Directories and System Identity

| Variable | Default | Description |
|----------|---------|-------------|
| `pki_agent_config_dir` | `/etc/openbao-agent.d` | Directory for `agent.hcl` and the credential files (`role_id`, `secret_id`, `token`). Owned by `pki_agent_user:pki_agent_group`, mode `0750` |
| `pki_agent_data_dir` | `/var/lib/openbao-agent` | Working directory for the agent. Used as the home directory for `pki_agent_user`. Stores the cached agent token at `agent-token` |
| `pki_agent_log_dir` | `/var/log/openbao-agent` | Log directory. The agent writes to the systemd journal (`SyslogIdentifier=openbao-agent`); this directory is created but not actively written to by the agent itself |
| `pki_agent_user` | `openbao-agent` | System user the agent daemon runs as. Created as a no-login system user |
| `pki_agent_group` | `openbao-agent` | System group for the agent daemon |

### Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `pki_agent_auto_auth_method` | `"approle"` | Authentication method: `"approle"` or `"token"`. The role fails preflight if an invalid value is supplied |

#### AppRole authentication (default)

Used when `pki_agent_auto_auth_method` is `"approle"`.

| Variable | Default | Description |
|----------|---------|-------------|
| `pki_agent_approle_role_id` | `""` | **Required for AppRole.** The AppRole `role_id`. Written to `{{ pki_agent_config_dir }}/role_id` |
| `pki_agent_approle_secret_id` | `""` | Inline `secret_id` value. Provide exactly one of `pki_agent_approle_secret_id` or `pki_agent_approle_secret_id_file` — the role fails preflight if both are empty |
| `pki_agent_approle_secret_id_file` | `""` | Path to a file on the target host that contains the `secret_id`. Use this when you manage the `secret_id` through an external secrets manager and deliver it to the host separately |

> **Warning:** Store `pki_agent_approle_secret_id` in Ansible Vault — never in plain-text inventory or playbook files. If `pki_agent_approle_secret_id_file` is used instead, ensure the file is mode `0600` and owned by `pki_agent_user` before the role runs.

#### Token authentication

Used when `pki_agent_auto_auth_method` is `"token"`.

| Variable | Default | Description |
|----------|---------|-------------|
| `pki_agent_token` | `""` | **Required for token auth.** A renewable OpenBao token with the required PKI capabilities. Written to `{{ pki_agent_config_dir }}/token`. The role fails preflight if this is empty when token auth is selected |

> **Warning:** Token auth is suitable for development or bootstrapping. For production, use AppRole — tokens have a fixed lifetime and require manual renewal if the agent is stopped for longer than the token TTL.

### Certificate List

| Variable | Default | Description |
|----------|---------|-------------|
| `pki_agent_certificates` | `[]` | **Required.** List of certificate entries to manage. MUST contain at least one entry — the role fails preflight if the list is empty. See [Certificate Entry Schema](#certificate-entry-schema) for all fields |

### Service Management

| Variable | Default | Description |
|----------|---------|-------------|
| `pki_agent_service_enabled` | `true` | Whether the `openbao-agent` systemd service is enabled at boot |
| `pki_agent_service_state` | `"started"` | Desired runtime state of the service: `started`, `stopped`, or `restarted` |

## Certificate Entry Schema

Each item in `pki_agent_certificates` is a map. The role generates one pair of `template {}` blocks in `agent.hcl` for each entry — one for the certificate (plus CA chain) and one for the private key. An optional third block writes the issuing CA certificate alone.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | — | Logical label for this certificate. Used as a comment header in `agent.hcl`. Must be unique within the list |
| `pki_mount` | string | Yes | — | Mount path of the PKI secrets engine — example: `"pki"`, `"pki/cassandra"` |
| `pki_role` | string | Yes | — | PKI role name — example: `"cassandra-node"`. The agent calls `{{ pki_mount }}/issue/{{ pki_role }}` |
| `common_name` | string | Yes | — | Certificate Common Name (CN) — example: `"cassandra-node-1.dc1.example.com"` |
| `alt_names` | string | No | `""` | Comma-separated DNS Subject Alternative Names — example: `"cassandra-node-1,cassandra-node-1.dc1"`. Omitted from the template call when empty |
| `ip_sans` | string | No | `""` | Comma-separated IP Subject Alternative Names — example: `"10.0.1.11,127.0.0.1"`. Omitted from the template call when empty |
| `ttl` | string | No | `"72h"` | Requested certificate TTL — example: `"24h"`, `"168h"`. MUST NOT exceed the PKI role's `max_ttl`. The agent renews before this expires |
| `cert_path` | string | Yes | — | Absolute path on the target host where the certificate PEM (including the issuing CA chain) is written |
| `key_path` | string | Yes | — | Absolute path on the target host where the private key PEM is written |
| `ca_path` | string | No | `""` | Absolute path on the target host where the issuing CA certificate is written alone. No CA template block is rendered when empty |
| `cert_owner` | string | No | `"root"` | Owner of `cert_path` and `ca_path` |
| `cert_group` | string | No | `"root"` | Group of `cert_path` and `ca_path` |
| `cert_mode` | string | No | `"0640"` | File mode for `cert_path` and `ca_path` |
| `key_mode` | string | No | `"0600"` | File mode for `key_path`. SHOULD remain `0600` — the private key MUST NOT be world-readable |
| `reload_command` | string | No | `""` | Shell command the agent runs after writing a new certificate. Executed via `sh -c`. No `exec {}` block is written when empty |
| `reload_timeout` | string | No | `"5s"` | Timeout for `reload_command`. Ignored when `reload_command` is empty |

The `cert_path` file contains both the leaf certificate and the issuing CA certificate, concatenated — suitable for services that expect a full chain. Use `ca_path` in addition if the consuming service requires the CA separately.

## How It Works

The role renders `agent.hcl` from the Jinja2 template and installs it to `{{ pki_agent_config_dir }}/agent.hcl`. The configuration contains:

1. **`bao {}`** — the OpenBao server address and optional namespace
2. **`auto_auth {}`** — AppRole or token authentication, plus a `sink "file" {}` block that caches the agent's own token to `{{ pki_agent_data_dir }}/agent-token`
3. **One `template {}` block per certificate field** — the agent evaluates the `pkiCert` template function to issue the certificate from the PKI secrets engine and write it to disk. The agent re-evaluates automatically when the certificate approaches expiry

The systemd unit (`openbao-agent.service`) runs as `pki_agent_user` with `NoNewPrivileges=true`, `PrivateTmp=true`, and `ProtectSystem=full`. It starts after `network-online.target` and restarts on failure with a 5-second back-off.

When `reload_command` is set for a certificate, the agent runs that command in a subprocess after each successful certificate rotation — this is the mechanism for restarting the service that consumes the certificate.

Credential files (`role_id`, `secret_id`, `token`) are written to `pki_agent_config_dir` by your playbook or secrets manager before the role runs — the role does not write them directly; it writes their paths into `agent.hcl` so that the agent process reads them at startup.

> **Note:** The role writes `role_id` and `secret_id` values into the config directory only through the `agent.hcl` template path references. You MUST ensure those files exist on the target host before the agent service starts. The examples below show how to create them in a `pre_tasks` block.

## Binary Install

When `pki_agent_install_method` is `"binary"`, the role:

1. Queries `https://api.github.com/repos/openbao/openbao/releases/latest` to resolve the version when `pki_agent_version` is empty
2. Downloads `bao_{{ version }}_linux_amd64.zip` from the GitHub releases page
3. Extracts the `bao` binary to `/usr/local/bin/`
4. Installs `unzip` via the OS package manager if not present

The binary method always targets `linux_amd64`. It skips the download if the installed `bao version` output already contains the requested version string.

> **Note:** The package method (`pkg`) is RECOMMENDED for production. It sets up the official OpenBao APT or YUM repository and installs the signed `openbao` package, which places the binary at `/usr/bin/bao`. The systemd unit references `/usr/bin/bao` regardless of install method — ensure your `PATH` or a symlink resolves correctly when using binary install on non-standard paths.

## Example Playbooks

### Basic Single-Certificate Setup with AppRole

The minimum configuration to issue one certificate via AppRole authentication. The `pre_tasks` block writes the AppRole credentials to disk — the agent reads them from files, not environment variables.

```yaml
- name: Deploy OpenBao Agent for node TLS
  hosts: app_servers
  become: true

  pre_tasks:
    - name: Write AppRole role_id
      ansible.builtin.copy:
        content: "{{ pki_approle_role_id }}"
        dest: /etc/openbao-agent.d/role_id
        owner: openbao-agent
        group: openbao-agent
        mode: "0640"

    - name: Write AppRole secret_id
      ansible.builtin.copy:
        content: "{{ pki_approle_secret_id }}"
        dest: /etc/openbao-agent.d/secret_id
        owner: openbao-agent
        group: openbao-agent
        mode: "0640"
      no_log: true

  roles:
    - role: axonops.axonops.pki_agent
      vars:
        pki_agent_addr: "https://openbao.internal.example.com:8200"
        pki_agent_auto_auth_method: approle
        pki_agent_approle_role_id: "{{ pki_approle_role_id }}"
        pki_agent_approle_secret_id: "{{ pki_approle_secret_id }}"
        pki_agent_certificates:
          - name: node-tls
            pki_mount: pki
            pki_role: app-server-node
            common_name: "{{ inventory_hostname }}.internal.example.com"
            ttl: 72h
            cert_path: /etc/ssl/app/node.crt
            key_path: /etc/ssl/app/node.key
            ca_path: /etc/ssl/app/ca.crt
```

> **Note:** The `pre_tasks` block MUST run before the role so the agent service can authenticate immediately on first start. The role creates the `openbao-agent` user and directories — if `pre_tasks` writes credential files before the user exists, either create the user first or use `post_tasks` and restart the service after writing credentials.

### Multi-Certificate Setup — Node and Client Certificates

Issue separate certificates for internode communication (higher TTL, IP SANs) and client connections (shorter TTL, DNS SANs only). The `reload_command` restarts the application after each rotation.

```yaml
- name: Deploy OpenBao Agent for Cassandra TLS
  hosts: cassandra
  become: true

  roles:
    - role: axonops.axonops.pki_agent
      vars:
        pki_agent_addr: "https://openbao.internal.example.com:8200"
        pki_agent_auto_auth_method: approle
        pki_agent_approle_role_id: "{{ vault_pki_role_id }}"
        pki_agent_approle_secret_id: "{{ vault_pki_secret_id }}"
        pki_agent_certificates:
          - name: cassandra-internode
            pki_mount: pki/cassandra
            pki_role: internode
            common_name: "{{ inventory_hostname }}.dc1.internal.example.com"
            alt_names: "{{ inventory_hostname }},{{ inventory_hostname }}.dc1"
            ip_sans: "{{ ansible_default_ipv4.address }},127.0.0.1"
            ttl: 168h
            cert_path: /opt/ssl/cassandra/internode.crt
            key_path: /opt/ssl/cassandra/internode.key
            ca_path: /opt/ssl/cassandra/ca.crt
            cert_owner: cassandra
            cert_group: cassandra
            cert_mode: "0640"
            key_mode: "0600"
            reload_command: "systemctl reload cassandra || systemctl restart cassandra"
            reload_timeout: "30s"

          - name: cassandra-client
            pki_mount: pki/cassandra
            pki_role: client
            common_name: "cql-client.dc1.internal.example.com"
            alt_names: "cql-client,cql-client.dc1"
            ttl: 48h
            cert_path: /opt/ssl/cassandra/client.crt
            key_path: /opt/ssl/cassandra/client.key
            cert_owner: cassandra
            cert_group: cassandra
            cert_mode: "0640"
            key_mode: "0600"
```

### Token Authentication

Use a long-lived OpenBao token instead of AppRole. Suitable for bootstrapping or environments where AppRole setup is not yet in place.

```yaml
- name: Deploy OpenBao Agent with token auth
  hosts: monitoring_nodes
  become: true

  pre_tasks:
    - name: Write OpenBao token
      ansible.builtin.copy:
        content: "{{ vault_openbao_token }}"
        dest: /etc/openbao-agent.d/token
        owner: openbao-agent
        group: openbao-agent
        mode: "0640"
      no_log: true

  roles:
    - role: axonops.axonops.pki_agent
      vars:
        pki_agent_addr: "https://openbao.internal.example.com:8200"
        pki_agent_auto_auth_method: token
        pki_agent_token: "{{ vault_openbao_token }}"
        pki_agent_certificates:
          - name: monitoring-tls
            pki_mount: pki
            pki_role: monitoring-client
            common_name: "prometheus-scraper.internal.example.com"
            ttl: 24h
            cert_path: /etc/ssl/monitoring/client.crt
            key_path: /etc/ssl/monitoring/client.key
            ca_path: /etc/ssl/monitoring/ca.crt
            cert_mode: "0644"
            key_mode: "0600"
```

### IP SANs and DNS alt_names

Include both IP addresses and DNS names in the SAN extension. This is required when services verify the server certificate against an IP address rather than a hostname.

```yaml
pki_agent_certificates:
  - name: api-server-tls
    pki_mount: pki
    pki_role: api-server
    common_name: "api-server-1.prod.example.com"
    alt_names: "api-server-1,api.prod.example.com,api.example.com"
    ip_sans: "10.0.10.55,192.168.1.10,127.0.0.1"
    ttl: 72h
    cert_path: /etc/ssl/api/server.crt
    key_path: /etc/ssl/api/server.key
    ca_path: /etc/ssl/api/ca.crt
    cert_owner: api
    cert_group: api
    cert_mode: "0640"
    key_mode: "0600"
    reload_command: "systemctl reload api-server"
    reload_timeout: "15s"
```

### reload_command for Service Restart After Rotation

The agent runs `reload_command` immediately after writing a new certificate. Use this to signal your service to reload its TLS context without a full restart where the service supports it, or to restart it if reload is not supported.

```yaml
pki_agent_certificates:
  - name: nginx-tls
    pki_mount: pki
    pki_role: web-server
    common_name: "www.example.com"
    alt_names: "example.com,www.example.com"
    ttl: 72h
    cert_path: /etc/nginx/ssl/server.crt
    key_path: /etc/nginx/ssl/server.key
    ca_path: /etc/nginx/ssl/ca.crt
    cert_owner: root
    cert_group: www-data
    cert_mode: "0640"
    key_mode: "0640"
    reload_command: "nginx -t && systemctl reload nginx"
    reload_timeout: "10s"
```

The command runs with `sh -c` and times out after `reload_timeout`. If the command exits non-zero or times out, the agent logs the failure but does not remove the newly written certificate. The next rotation attempt will retry the command.

### Binary Install Instead of Package Manager

Use `pki_agent_install_method: binary` when the OpenBao package repository is not reachable or when you need a specific build not yet in the package feeds.

```yaml
- name: Deploy OpenBao Agent via binary download
  hosts: air_gapped_nodes
  become: true

  roles:
    - role: axonops.axonops.pki_agent
      vars:
        pki_agent_install_method: binary
        pki_agent_version: "2.1.0"
        pki_agent_addr: "https://openbao.internal.example.com:8200"
        pki_agent_auto_auth_method: approle
        pki_agent_approle_role_id: "{{ vault_pki_role_id }}"
        pki_agent_approle_secret_id: "{{ vault_pki_secret_id }}"
        pki_agent_certificates:
          - name: service-tls
            pki_mount: pki
            pki_role: service-node
            common_name: "{{ inventory_hostname }}.internal.example.com"
            ttl: 72h
            cert_path: /etc/ssl/service/server.crt
            key_path: /etc/ssl/service/server.key
```

Pinning `pki_agent_version` is REQUIRED when using binary install in a CI/CD pipeline. Omitting it causes the role to query the GitHub API on every run and download the latest release, which can change the installed binary mid-pipeline without warning.

### Custom Directories and User/Group

Override all path and identity defaults — useful when integrating with a host that enforces a specific directory layout or runs multiple agents under different accounts.

```yaml
- name: Deploy OpenBao Agent with custom directories
  hosts: data_plane
  become: true

  roles:
    - role: axonops.axonops.pki_agent
      vars:
        pki_agent_config_dir: /opt/openbao-agent/config
        pki_agent_data_dir: /opt/openbao-agent/data
        pki_agent_log_dir: /opt/openbao-agent/logs
        pki_agent_user: svc-openbao
        pki_agent_group: svc-openbao
        pki_agent_addr: "https://openbao.internal.example.com:8200"
        pki_agent_auto_auth_method: approle
        pki_agent_approle_role_id: "{{ vault_pki_role_id }}"
        pki_agent_approle_secret_id: "{{ vault_pki_secret_id }}"
        pki_agent_certificates:
          - name: data-plane-tls
            pki_mount: pki
            pki_role: data-plane-node
            common_name: "{{ inventory_hostname }}.data.example.com"
            ttl: 72h
            cert_path: /opt/tls/data-plane/server.crt
            key_path: /opt/tls/data-plane/server.key
            ca_path: /opt/tls/data-plane/ca.crt
            cert_owner: svc-openbao
            cert_group: svc-openbao
```

### secret_id_file Instead of Inline secret_id

Deliver the `secret_id` to the host through an external secrets manager (for example HashiCorp Vault Secrets, AWS Secrets Manager, or a CI/CD pipeline step) and tell the agent to read it from a file. This avoids the `secret_id` value ever appearing in Ansible variable scope.

```yaml
- name: Deploy OpenBao Agent with secret_id from file
  hosts: production_nodes
  become: true

  roles:
    - role: axonops.axonops.pki_agent
      vars:
        pki_agent_addr: "https://openbao.internal.example.com:8200"
        pki_agent_auto_auth_method: approle
        pki_agent_approle_role_id: "{{ vault_pki_role_id }}"
        # secret_id is delivered to this path by an external process before the play runs.
        # The file must exist and be readable by pki_agent_user when the agent starts.
        pki_agent_approle_secret_id_file: /run/secrets/openbao-secret-id
        pki_agent_certificates:
          - name: production-tls
            pki_mount: pki
            pki_role: production-node
            common_name: "{{ inventory_hostname }}.prod.example.com"
            ttl: 72h
            cert_path: /etc/ssl/production/server.crt
            key_path: /etc/ssl/production/server.key
            ca_path: /etc/ssl/production/ca.crt
            cert_owner: root
            cert_group: root
            cert_mode: "0644"
            key_mode: "0600"
```

When `pki_agent_approle_secret_id_file` is non-empty, its value is written directly into `agent.hcl` as `secret_id_file_path`. The inline `pki_agent_approle_secret_id` is ignored. The role does not validate that the file exists on the target host at converge time — if the file is absent when the agent starts, authentication fails and the agent logs `secret_id file not found`.

### Integration with Cassandra TLS

This role pairs with the `cassandra` role when Cassandra is configured to use PEM-based TLS (`PEMBasedSslContextFactory`). The agent writes certificates directly to the paths Cassandra reads at startup and on reload.

```yaml
- name: Deploy Cassandra with automated certificate rotation
  hosts: cassandra
  become: true

  vars:
    # pki_agent variables
    pki_agent_addr: "https://openbao.internal.example.com:8200"
    pki_agent_auto_auth_method: approle
    pki_agent_approle_role_id: "{{ vault_pki_role_id }}"
    pki_agent_approle_secret_id: "{{ vault_pki_secret_id }}"
    pki_agent_certificates:
      - name: cassandra-internode
        pki_mount: pki/cassandra
        pki_role: internode
        common_name: "{{ inventory_hostname }}.dc1.internal.example.com"
        alt_names: "{{ inventory_hostname }}"
        ip_sans: "{{ ansible_default_ipv4.address }}"
        ttl: 168h
        cert_path: /opt/ssl/cassandra/internode.crt
        key_path: /opt/ssl/cassandra/internode.key
        ca_path: /opt/ssl/cassandra/ca.crt
        cert_owner: cassandra
        cert_group: cassandra
        cert_mode: "0640"
        key_mode: "0600"
        reload_command: "systemctl restart cassandra"
        reload_timeout: "60s"

    # cassandra variables — match the cert paths above
    cassandra_ssl_path: /opt/ssl/cassandra
    cassandra_ssl_internode_encryption: "all"
    cassandra_ssl_internode_require_client_auth: true

  roles:
    - role: axonops.axonops.pki_agent
    - role: axonops.axonops.cassandra
```

The `pki_agent` role MUST run before the `cassandra` role in this play so that the agent service is running and has issued the initial certificates before Cassandra starts. Cassandra will fail to start if it reads empty certificate files.

### Integration with OpenSearch TLS

Use the `custom` TLS mode of the `opensearch` role alongside `pki_agent` to supply externally managed certificates. The agent writes the certificate files to the paths the `opensearch` role reads from the control node.

For the `opensearch` role's `custom` TLS mode, certificate files are copied from the **control node** — not the target. The recommended pattern is to run `pki_agent` first to populate certificates on the target, then use those files in a subsequent play that treats those target paths as the control-node source. Alternatively, issue the OpenSearch certificates in advance and supply them to `opensearch_tls_*` variables directly.

The following example issues per-node HTTP and transport certificates and restarts OpenSearch after each rotation:

```yaml
- name: Deploy OpenBao Agent for OpenSearch TLS
  hosts: opensearch
  become: true

  roles:
    - role: axonops.axonops.pki_agent
      vars:
        pki_agent_addr: "https://openbao.internal.example.com:8200"
        pki_agent_auto_auth_method: approle
        pki_agent_approle_role_id: "{{ vault_pki_role_id }}"
        pki_agent_approle_secret_id: "{{ vault_pki_secret_id }}"
        pki_agent_certificates:
          - name: opensearch-transport
            pki_mount: pki/opensearch
            pki_role: transport-node
            common_name: "{{ inventory_hostname }}.search.internal.example.com"
            alt_names: "{{ inventory_hostname }}"
            ip_sans: "{{ ansible_default_ipv4.address }}"
            ttl: 168h
            cert_path: /usr/share/opensearch/config/transport.crt
            key_path: /usr/share/opensearch/config/transport.key
            ca_path: /usr/share/opensearch/config/root-ca.crt
            cert_owner: opensearch
            cert_group: opensearch
            cert_mode: "0640"
            key_mode: "0600"
            reload_command: "systemctl restart opensearch"
            reload_timeout: "90s"

          - name: opensearch-http
            pki_mount: pki/opensearch
            pki_role: http-node
            common_name: "{{ inventory_hostname }}.search.internal.example.com"
            alt_names: "{{ inventory_hostname }},opensearch.internal.example.com"
            ip_sans: "{{ ansible_default_ipv4.address }}"
            ttl: 168h
            cert_path: /usr/share/opensearch/config/http.crt
            key_path: /usr/share/opensearch/config/http.key
            cert_owner: opensearch
            cert_group: opensearch
            cert_mode: "0640"
            key_mode: "0600"
```

## OpenBao Server Setup Reference

The role does not configure the OpenBao server. The following policy and AppRole configuration is the minimum required to issue certificates. Apply this to your OpenBao server before running the role.

```bash
# Enable the PKI secrets engine
bao secrets enable -path=pki pki
bao secrets tune -max-lease-ttl=87600h pki

# Generate a root CA (or import your own)
bao write pki/root/generate/internal \
  common_name="Example Internal CA" \
  ttl=87600h

# Configure the PKI role
bao write pki/roles/my-service \
  allowed_domains="internal.example.com" \
  allow_subdomains=true \
  allow_ip_sans=true \
  max_ttl=168h

# Create the issuance policy
bao policy write pki-issue - <<EOF
path "pki/issue/*"  { capabilities = ["create", "update"] }
path "pki/sign/*"   { capabilities = ["create", "update"] }
EOF

# Enable AppRole and create a role
bao auth enable approle
bao write auth/approle/role/my-service \
  policies="pki-issue" \
  token_ttl=1h \
  token_max_ttl=4h

# Retrieve credentials
bao read auth/approle/role/my-service/role-id
bao write -f auth/approle/role/my-service/secret-id
```

## Testing

The role is tested with [Molecule](https://ansible.readthedocs.io/projects/molecule/) using a Docker driver. The default scenario starts a real OpenBao dev-mode server alongside the agent container, bootstraps AppRole and a PKI engine, runs the role, and verifies that certificates are issued and the service is running.

```bash
molecule test -s default
```

The scenario uses the `geerlingguy/docker-rockylinux9-ansible` image by default. Override the distribution with `MOLECULE_DISTRO`:

```bash
MOLECULE_DISTRO=ubuntu2204 molecule test -s default
```

The verify playbook checks:

- `/usr/bin/bao` exists and is executable
- `agent.hcl` is present, owned by `openbao-agent`, and contains a `bao {}` stanza
- The `openbao-agent` systemd service is enabled and active
- Each certificate and key file exists at the configured path with the correct mode
- `exec {}` blocks appear only for certificates that have `reload_command` set

## License

Apache 2.0 — see the collection `LICENSE` file.

## Author

AxonOps Limited
