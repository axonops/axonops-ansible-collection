# pki_agent Role

## Overview

The `pki_agent` role installs and configures [OpenBao Agent](https://openbao.org/docs/agent-and-proxy/agent) for automated PKI certificate lifecycle management. The agent authenticates to an OpenBao server, issues X.509 certificates via the PKI secrets engine, writes them to disk, and rotates them automatically before expiry — no cron jobs and no manual renewals. This role is OpenBao-only; HashiCorp Vault is not supported.

## Requirements

- Ansible 2.10 or higher
- OpenBao server reachable from each target host, with the PKI secrets engine mounted and an AppRole or token credential with `create`/`update` capability on the relevant `pki/issue/*` or `pki/sign/*` paths
- Target system running a systemd-based Linux distribution — see supported platforms below

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
| `pki_agent_version` | `""` | OpenBao package version to install. Empty string installs the latest available version. Pinning a version is RECOMMENDED for production — example: `"2.1.0"` |
| `pki_agent_install_method` | `"pkg"` | Install method: `pkg` (OS package manager, adds the official OpenBao repository) or `binary` (downloads a release zip from GitHub). The `pkg` method is RECOMMENDED for production |

### OpenBao Server Connection

| Variable | Default | Description |
|----------|---------|-------------|
| `pki_agent_addr` | `""` | **Required.** URL of the OpenBao server — example: `"https://openbao.internal.example.com:8200"`. The role fails immediately if this is empty |
| `pki_agent_namespace` | `""` | OpenBao namespace. Omitted from the configuration when empty |

### Directories and System Identity

| Variable | Default | Description |
|----------|---------|-------------|
| `pki_agent_config_dir` | `/etc/openbao-agent.d` | Directory for `agent.hcl` and credential files (`role_id`, `secret_id`, `token`). Owned by `pki_agent_user:pki_agent_group`, mode `0750` |
| `pki_agent_data_dir` | `/var/lib/openbao-agent` | Working directory for the agent daemon. Stores the cached agent token |
| `pki_agent_log_dir` | `/var/log/openbao-agent` | Log directory. The agent writes to the systemd journal; this directory is created but not actively written to by the agent |
| `pki_agent_user` | `openbao-agent` | System user the agent daemon runs as. Created as a no-login system user |
| `pki_agent_group` | `openbao-agent` | System group for the agent daemon |

### Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `pki_agent_auto_auth_method` | `"approle"` | Authentication method: `"approle"` or `"token"`. The role fails preflight if an invalid value is supplied |

#### AppRole Authentication (default)

Used when `pki_agent_auto_auth_method` is `"approle"`.

| Variable | Default | Description |
|----------|---------|-------------|
| `pki_agent_approle_role_id` | `""` | **Required for AppRole.** The AppRole `role_id`. Written to `{{ pki_agent_config_dir }}/role_id` |
| `pki_agent_approle_secret_id` | `""` | Inline `secret_id` value. Provide exactly one of `pki_agent_approle_secret_id` or `pki_agent_approle_secret_id_file` — the role fails preflight if both are empty |
| `pki_agent_approle_secret_id_file` | `""` | Path to a file on the target host containing the `secret_id`. Use this when the `secret_id` is delivered by an external secrets manager |

> **Warning:** Store `pki_agent_approle_secret_id` in Ansible Vault — never in plain-text inventory or playbook files. If `pki_agent_approle_secret_id_file` is used instead, the file MUST be mode `0600` and owned by `pki_agent_user` before the role runs.

#### Token Authentication

Used when `pki_agent_auto_auth_method` is `"token"`.

| Variable | Default | Description |
|----------|---------|-------------|
| `pki_agent_token` | `""` | **Required for token auth.** A renewable OpenBao token with the required PKI capabilities. Written to `{{ pki_agent_config_dir }}/token`. The role fails preflight if this is empty when token auth is selected |

> **Warning:** Token auth is suitable for development or bootstrapping only. For production, use AppRole — tokens have a fixed lifetime and require manual renewal if the agent is stopped for longer than the token TTL.

### Certificate List

| Variable | Default | Description |
|----------|---------|-------------|
| `pki_agent_certificates` | `[]` | **Required.** List of certificate entries to manage. MUST contain at least one entry — the role fails preflight if the list is empty |

### Service Management

| Variable | Default | Description |
|----------|---------|-------------|
| `pki_agent_service_enabled` | `true` | Whether the `openbao-agent` systemd service is enabled at boot |
| `pki_agent_service_state` | `"started"` | Desired runtime state of the service: `started`, `stopped`, or `restarted` |

## Certificate Entry Schema

Each item in `pki_agent_certificates` is a map. The role generates one pair of `template {}` blocks in `agent.hcl` per entry — one for the certificate (including the issuing CA chain) and one for the private key. An optional third block writes the issuing CA certificate alone.

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | — | Logical label for this certificate. Used as a comment header in `agent.hcl`. Must be unique within the list |
| `pki_mount` | string | Yes | — | Mount path of the PKI secrets engine — example: `"pki"`, `"pki/cassandra"` |
| `pki_role` | string | Yes | — | PKI role name — example: `"cassandra-node"`. The agent calls `{{ pki_mount }}/issue/{{ pki_role }}` |
| `common_name` | string | Yes | — | Certificate Common Name (CN) — example: `"node-1.dc1.example.com"` |
| `alt_names` | string | No | `""` | Comma-separated DNS Subject Alternative Names. Omitted when empty |
| `ip_sans` | string | No | `""` | Comma-separated IP Subject Alternative Names. Omitted when empty |
| `ttl` | string | No | `"72h"` | Requested certificate TTL — example: `"24h"`, `"168h"`. MUST NOT exceed the PKI role's `max_ttl` |
| `cert_path` | string | Yes | — | Absolute path on the target host where the certificate PEM (including the issuing CA chain) is written |
| `key_path` | string | Yes | — | Absolute path on the target host where the private key PEM is written |
| `ca_path` | string | No | `""` | Absolute path where the issuing CA certificate is written alone. No CA template block is rendered when empty |
| `cert_owner` | string | No | `"root"` | Owner of `cert_path` and `ca_path` |
| `cert_group` | string | No | `"root"` | Group of `cert_path` and `ca_path` |
| `cert_mode` | string | No | `"0640"` | File mode for `cert_path` and `ca_path` |
| `key_mode` | string | No | `"0600"` | File mode for `key_path`. SHOULD remain `0600` — the private key MUST NOT be world-readable |
| `reload_command` | string | No | `""` | Shell command the agent runs after writing a new certificate. Executed via `sh -c`. No `exec {}` block is written when empty |
| `reload_timeout` | string | No | `"5s"` | Timeout for `reload_command`. Ignored when `reload_command` is empty |

The `cert_path` file contains both the leaf certificate and the issuing CA certificate concatenated, suitable for services that expect a full chain. Set `ca_path` as well if the consuming service requires the CA certificate separately.

## Example Playbooks

### Basic Single-Certificate Setup with AppRole

The minimum configuration to issue one certificate via AppRole authentication. The `pre_tasks` block writes the AppRole credentials to disk before the role runs — the agent reads them from files at startup.

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

> **Note:** The `pre_tasks` block MUST run before the role so the agent can authenticate on first start. The role creates the `openbao-agent` user and config directory — if `pre_tasks` writes credential files before the user exists, place a `user` task first or deliver credentials after the role completes and restart the service.

### Multiple Certificates

Issue separate certificates for different purposes within the same agent instance. Each entry results in an independent template pair in `agent.hcl` and is renewed independently.

```yaml
- name: Deploy OpenBao Agent with multiple certificates
  hosts: app_servers
  become: true

  roles:
    - role: axonops.axonops.pki_agent
      vars:
        pki_agent_addr: "https://openbao.internal.example.com:8200"
        pki_agent_auto_auth_method: approle
        pki_agent_approle_role_id: "{{ vault_pki_role_id }}"
        pki_agent_approle_secret_id: "{{ vault_pki_secret_id }}"
        pki_agent_certificates:
          - name: server-tls
            pki_mount: pki
            pki_role: server-node
            common_name: "{{ inventory_hostname }}.internal.example.com"
            alt_names: "{{ inventory_hostname }}"
            ip_sans: "{{ ansible_default_ipv4.address }},127.0.0.1"
            ttl: 168h
            cert_path: /etc/ssl/server/node.crt
            key_path: /etc/ssl/server/node.key
            ca_path: /etc/ssl/server/ca.crt
            cert_owner: appuser
            cert_group: appuser
            cert_mode: "0640"
            key_mode: "0600"
            reload_command: "systemctl reload my-service || systemctl restart my-service"
            reload_timeout: "30s"

          - name: client-tls
            pki_mount: pki
            pki_role: client
            common_name: "client.internal.example.com"
            ttl: 48h
            cert_path: /etc/ssl/client/client.crt
            key_path: /etc/ssl/client/client.key
            cert_owner: appuser
            cert_group: appuser
            cert_mode: "0640"
            key_mode: "0600"
```

### Token Authentication

Use a long-lived OpenBao token instead of AppRole. Suitable for bootstrapping or environments where AppRole is not yet configured.

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

## Integration with Cassandra TLS

The `pki_agent` role pairs with the `cassandra` role when Cassandra uses `PEMBasedSslContextFactory` for TLS. This factory reads PEM files directly, without requiring JKS keystores. `PEMBasedSslContextFactory` is available in Cassandra 5.x — it is not supported in Cassandra 4.x or 3.x.

The agent writes certificate files to the paths that Cassandra reads at startup and on reload. `pki_agent` MUST appear before `cassandra` in the role list — Cassandra fails to start if it finds empty certificate files.

Set `cert_owner` and `cert_group` to `cassandra` so the Cassandra process can read the private key.

```yaml
- name: Deploy Cassandra with automated certificate rotation
  hosts: cassandra
  become: true

  vars:
    # OpenBao Agent — issues and rotates PEM certificates
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

      - name: cassandra-client
        pki_mount: pki/cassandra
        pki_role: client
        common_name: "cql-client.dc1.internal.example.com"
        ttl: 48h
        cert_path: /opt/ssl/cassandra/client.crt
        key_path: /opt/ssl/cassandra/client.key
        cert_owner: cassandra
        cert_group: cassandra
        cert_mode: "0640"
        key_mode: "0600"

    # Cassandra — PEM-based TLS, paths match the cert entries above
    cassandra_ssl_path: /opt/ssl/cassandra
    cassandra_ssl_internode_encryption: all
    cassandra_ssl_internode_require_client_auth: true
    cassandra_ssl_client_encryption_enabled: true

  roles:
    - role: axonops.axonops.pki_agent
    - role: axonops.axonops.java
      vars:
        java_pkg: java-17-openjdk-headless
    - role: axonops.axonops.cassandra
```

The Cassandra `cassandra.yaml` template MUST reference `PEMBasedSslContextFactory` and point to the PEM paths. Add the following to your Cassandra configuration when using this integration:

```yaml
server_encryption_options:
  internode_encryption: all
  ssl_context_factory:
    class_name: org.apache.cassandra.security.PEMBasedSslContextFactory
    parameters:
      private_key: /opt/ssl/cassandra/internode.key
      private_key_password: ""
      public_certificate: /opt/ssl/cassandra/internode.crt
      trusted_certificates: /opt/ssl/cassandra/ca.crt
  require_client_auth: true
```

> **Note:** The `reload_command` in the `cassandra-internode` certificate entry restarts Cassandra after each rotation. Cassandra does not support in-process TLS reload — a full service restart is required to pick up new certificates. Set `reload_timeout` to at least `60s` to allow the node to rejoin the cluster before the agent considers the command failed.

## Integration with OpenSearch TLS

The `opensearch` role's `custom` TLS mode (`opensearch_tls_mode: custom`) reads certificate files from the **control node** and copies them to each OpenSearch node. The `pki_agent` role writes certificates to the **target node**. These two behaviours require a bridging step — choose one of the following patterns based on your deployment.

### Pattern 1: Issue certs on each node, fetch back to control node

Run `pki_agent` on each OpenSearch node to issue per-node certificates, then fetch those files back to the control node before running the `opensearch` role. This is the correct pattern when each node needs a unique CN or IP SAN.

> **Warning:** The fetch step copies private keys from target nodes to the control node. Ensure the control node is trusted and restrict the staging directory permissions. Clean up fetched keys after the play completes if the control node is long-lived.

```yaml
# Play 1: Issue certificates on each OpenSearch node
- name: Issue OpenSearch TLS certificates
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

# Play 2: Fetch certs back to control node, then deploy OpenSearch
- name: Deploy OpenSearch with fetched certificates
  hosts: opensearch
  become: true

  pre_tasks:
    - name: Create staging directory on control node
      ansible.builtin.file:
        path: "/tmp/opensearch-certs/{{ inventory_hostname }}"
        state: directory
        mode: "0700"
      delegate_to: localhost
      become: false

    # flat: true prevents Ansible from adding an extra inventory_hostname/ subdirectory
    - name: Fetch node transport certificate to control node
      ansible.builtin.fetch:
        src: /usr/share/opensearch/config/transport.crt
        dest: "/tmp/opensearch-certs/{{ inventory_hostname }}/transport.crt"
        flat: true

    - name: Fetch node HTTP certificate to control node
      ansible.builtin.fetch:
        src: /usr/share/opensearch/config/http.crt
        dest: "/tmp/opensearch-certs/{{ inventory_hostname }}/http.crt"
        flat: true

    - name: Fetch node transport key to control node
      ansible.builtin.fetch:
        src: /usr/share/opensearch/config/transport.key
        dest: "/tmp/opensearch-certs/{{ inventory_hostname }}/transport.key"
        flat: true

    - name: Fetch node HTTP key to control node
      ansible.builtin.fetch:
        src: /usr/share/opensearch/config/http.key
        dest: "/tmp/opensearch-certs/{{ inventory_hostname }}/http.key"
        flat: true

    - name: Fetch root CA to control node
      ansible.builtin.fetch:
        src: /usr/share/opensearch/config/root-ca.crt
        dest: "/tmp/opensearch-certs/root-ca.crt"
        flat: true
      run_once: true

  roles:
    - role: axonops.axonops.opensearch
      vars:
        opensearch_tls_mode: custom
        opensearch_tls_root_ca: /tmp/opensearch-certs/root-ca.crt
        opensearch_tls_node_cert: "/tmp/opensearch-certs/{{ inventory_hostname }}/transport.crt"
        opensearch_tls_node_key: "/tmp/opensearch-certs/{{ inventory_hostname }}/transport.key"
        opensearch_tls_node_http_cert: "/tmp/opensearch-certs/{{ inventory_hostname }}/http.crt"
        opensearch_tls_node_http_key: "/tmp/opensearch-certs/{{ inventory_hostname }}/http.key"
        opensearch_admin_password: "{{ vault_opensearch_admin_password }}"
        opensearch_tls_admin_dn: "CN=admin,OU=Ops,O=Example,DC=internal,DC=example,DC=com"
        opensearch_tls_node_dn: "CN=*.search.internal.example.com,OU=Ops,O=Example,DC=internal,DC=example,DC=com"

  post_tasks:
    - name: Clean up fetched keys from control node
      ansible.builtin.file:
        path: /tmp/opensearch-certs
        state: absent
      delegate_to: localhost
      become: false
      run_once: true
```

### Pattern 2: Issue all certs on the control node

If the OpenBao server is reachable from the Ansible control node, run `pki_agent` on localhost to issue certificates before running the `opensearch` role. This avoids the fetch step and is simpler when a shared wildcard certificate is acceptable for all nodes.

This pattern does not provide per-rotation restart for OpenSearch — use Pattern 1 if automated rotation with service restart is required.

The admin certificate is required by the OpenSearch role to initialise the security plugin. Issue it as a separate entry alongside a wildcard node certificate:

```yaml
- name: Issue OpenSearch certificates on control node
  hosts: localhost
  become: false

  roles:
    - role: axonops.axonops.pki_agent
      vars:
        pki_agent_addr: "https://openbao.internal.example.com:8200"
        pki_agent_auto_auth_method: approle
        pki_agent_approle_role_id: "{{ vault_pki_role_id }}"
        pki_agent_approle_secret_id: "{{ vault_pki_secret_id }}"
        pki_agent_certificates:
          - name: opensearch-node
            pki_mount: pki/opensearch
            pki_role: node-wildcard
            common_name: "*.search.internal.example.com"
            ttl: 168h
            cert_path: /tmp/opensearch-certs/node.crt
            key_path: /tmp/opensearch-certs/node.key
            ca_path: /tmp/opensearch-certs/root-ca.crt

          - name: opensearch-admin
            pki_mount: pki/opensearch
            pki_role: admin
            common_name: "admin.search.internal.example.com"
            ttl: 720h
            cert_path: /tmp/opensearch-certs/admin.crt
            key_path: /tmp/opensearch-certs/admin.key

- name: Deploy OpenSearch with control-node certificates
  hosts: opensearch
  become: true

  roles:
    - role: axonops.axonops.opensearch
      vars:
        opensearch_cluster_name: production
        opensearch_cluster_type: multi-node
        opensearch_admin_password: "{{ vault_opensearch_admin_password }}"
        opensearch_tls_mode: custom
        opensearch_tls_root_ca: /tmp/opensearch-certs/root-ca.crt
        opensearch_tls_admin_cert: /tmp/opensearch-certs/admin.crt
        opensearch_tls_admin_key: /tmp/opensearch-certs/admin.key
        opensearch_tls_node_cert: /tmp/opensearch-certs/node.crt
        opensearch_tls_node_key: /tmp/opensearch-certs/node.key
        opensearch_tls_node_http_cert: /tmp/opensearch-certs/node.crt
        opensearch_tls_node_http_key: /tmp/opensearch-certs/node.key
        opensearch_tls_admin_dn: "CN=admin.search.internal.example.com"
        opensearch_tls_node_dn: "CN=*.search.internal.example.com"
```

> **Note:** Pattern 2 uses a shared wildcard certificate for all nodes. The `opensearch_tls_node_dn` must match the CN issued above. Per-node certificates with unique CNs or IP SANs require Pattern 1.

## OpenBao Server Setup Reference

The role does not configure the OpenBao server. The following is the minimum server-side configuration required before running the role. Apply this once to your OpenBao server.

```bash
# Enable the PKI secrets engine
bao secrets enable -path=pki pki
bao secrets tune -max-lease-ttl=87600h pki

# Generate a root CA (or import your own)
bao write pki/root/generate/internal \
  common_name="Example Internal CA" \
  ttl=87600h

# Configure a PKI role for a service
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

# Enable AppRole and create a role bound to the policy
bao auth enable approle
bao write auth/approle/role/my-service \
  policies="pki-issue" \
  token_ttl=1h \
  token_max_ttl=4h

# Retrieve credentials for use in your playbook
bao read auth/approle/role/my-service/role-id
bao write -f auth/approle/role/my-service/secret-id
```

## Notes

- **Credential file ordering**: The role creates the `openbao-agent` user and config directory during the play. Any `pre_tasks` that write credential files MUST either run after the user is created or use the `become` directive with an appropriate user. The simplest approach is to place credential tasks after a task that creates the user explicitly.
- **Binary install on amd64 only**: The `binary` install method always downloads the `linux_amd64` build. ARM and other architectures MUST use the `pkg` install method.
- **`secret_id_file` validation**: When `pki_agent_approle_secret_id_file` is set, the role writes the path into `agent.hcl` but does not verify the file exists on the target. If the file is absent when the agent starts, authentication fails with `secret_id file not found` in the journal.
- **`reload_command` failure handling**: If the reload command exits non-zero or times out, the agent logs the failure but retains the newly written certificate. The command is retried at the next rotation cycle.
- **Systemd hardening**: The unit runs with `NoNewPrivileges=true`, `PrivateTmp=true`, and `ProtectSystem=full`. It starts after `network-online.target` and restarts on failure with a 5-second back-off.

## License

See the main collection LICENSE file.

## Author

AxonOps Limited
