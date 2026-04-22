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
