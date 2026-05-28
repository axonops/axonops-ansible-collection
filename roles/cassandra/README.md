# AxonOps Cassandra Ansible Role

Installs and configures Apache Cassandra from the Apache tar distribution.

## Requirements

- Java must be installed before running this role (use `axonops.axonops.java`).

## Configuration

Key variables (see `defaults/main.yml` for the full list):

```yaml
cassandra_cluster_name: default
cassandra_dc: default
cassandra_rack: rack1
cassandra_max_heap_size: 1G
```

## TLS

### JKS (default)

```yaml
cassandra_ssl_internode_encryption: all
cassandra_ssl_client_encryption_enabled: true
cassandra_ssl_internode_keystore_file: /etc/cassandra/conf/.keystore
cassandra_ssl_internode_keystore_pass: "{{ vault_keystore_password }}"
cassandra_ssl_truststore_file: /etc/cassandra/conf/.truststore
cassandra_ssl_truststore_pass: "{{ vault_truststore_password }}"
```

#### Password files (default behaviour — changed)

> **⚠ Behaviour change.** Prior to this release, the role embedded JKS passwords inline in `cassandra.yaml`. By default the role now writes each password to a separate mode `0600` file owned by the cassandra user and emits `keystore_password_file:` / `truststore_password_file:` keys in `cassandra.yaml` instead. This affects both `server_encryption_options` and `client_encryption_options`. No data is lost; running the role updates `cassandra.yaml` and Cassandra is restarted via the existing handler.

Password files are written only when (a) the relevant TLS path is enabled and (b) the configured password is non-empty. Four files are written by default under `cassandra_conf_dir`:

- `server_keystore_passwordfile.txt`
- `server_truststore_passwordfile.txt`
- `client_keystore_passwordfile.txt`
- `client_truststore_passwordfile.txt`

To opt out (keep the legacy inline behaviour):

```yaml
cassandra_use_password_files: false
```

See [docs/roles/cassandra.md](../../docs/roles/cassandra.md#password-files-default) for the full variable reference.

### PEM-based TLS (Cassandra 4.1+)

Set `cassandra_ssl_internode_ssl_context_factory: pem` (and/or `cassandra_ssl_client_ssl_context_factory: pem`) to use `PEMBasedSslContextFactory`.

Two modes are available:

**Inline mode** — pass PEM content as variable values (store in Ansible Vault):

```yaml
cassandra_ssl_internode_encryption: all
cassandra_ssl_internode_ssl_context_factory: pem
cassandra_ssl_internode_pem_private_key: "{{ vault_cassandra_internode_pem_key }}"
cassandra_ssl_internode_pem_trusted_certificates: "{{ vault_cassandra_internode_pem_ca }}"
```

**File mode** — leave `pem_private_key` empty and point `keystore_file` / `truststore_file` at PEM files on the target:

```yaml
cassandra_ssl_internode_encryption: all
cassandra_ssl_internode_ssl_context_factory: pem
cassandra_ssl_internode_keystore_file: /etc/cassandra/tls/node-combined.pem
cassandra_ssl_truststore_file: /etc/cassandra/tls/ca.pem
```

**Key requirements:**
- Private keys must be **PKCS#8** format (`-----BEGIN PRIVATE KEY-----`). Convert PKCS#1 keys with `openssl pkcs8 -topk8 -nocrypt -in server.key -out server-pkcs8.key`.
- `private_key` / `keystore_file` must contain the private key **and** certificate chain **concatenated** — Cassandra reads both from the same value.

Generate a PKCS#8 key and self-signed certificate:

```bash
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out node.key
openssl req -new -x509 -key node.key -out node.crt -days 365 -subj "/CN=$(hostname -f)"
cat node.key node.crt > node-combined.pem
```

See `defaults/main.yml` for the full list of PEM variables (`cassandra_ssl_internode_pem_*` and `cassandra_ssl_client_pem_*`). See [docs/roles/cassandra.md](../../docs/roles/cassandra.md) for detailed descriptions and additional examples.

## Example Playbook

```yaml
- hosts: cassandra
  roles:
    - role: axonops.axonops.java
    - role: axonops.axonops.cassandra
      vars:
        cassandra_cluster_name: my-cluster
        cassandra_dc: dc1
```
