# AxonOps Cassandra Ansible Role

Installs and configures Apache Cassandra from the Apache tar distribution.

## Supported versions

| Cassandra | Java | `cassandra.yaml` schema | JVM options file(s) |
|-----------|------|--------------------------|---------------------|
| 3.11.x    | 8    | Legacy (`*_in_ms`, `*_in_mb`) | `jvm.options` |
| 4.1.x     | 11   | Modern (duration/size strings) | `jvm-server.options`, `jvm11-server.options`, `jvm-clients.options`, `jvm11-clients.options` |
| 5.0.x     | 17   | Modern (duration/size strings) | `jvm-server.options`, `jvm11-server.options`, `jvm-clients.options`, `jvm11-clients.options`, `jvm17-server.options`, `jvm17-clients.options` |

Set `cassandra_version` to a value starting with `3.11`, `4.1`, or `5.` — anything
else makes the role fail fast at the version assertion.

The `axonops.axonops.java` role auto-selects the Java major version from
`cassandra_version` (Java 8 for 3.11, Java 11 for 4.1, Java 17 for 5.x); use
`java_use_zulu: true` on RHEL 10+ / Debian 13+ where the base repos no longer
ship the relevant OpenJDK package.

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

#### Password files (`cassandra_use_password_files`) — not supported

> **⚠ Not supported on this role's Cassandra versions.** The `keystore_password_file:` / `truststore_password_file:` keys were added in **Apache Cassandra 6.0** ([CASSANDRA-13428](https://issues.apache.org/jira/browse/CASSANDRA-13428)) and do **not** exist in Cassandra 4.1.x or 5.0.x — the only versions this role supports. On those versions Cassandra rejects the keys at startup with `Invalid yaml. Please remove properties [truststore_password_file, keystore_password_file]` and refuses to boot.

For this reason `cassandra_use_password_files` defaults to `false` and the role **force-disables it with a warning** if you set it `true`, falling back to inline `keystore_password:` / `truststore_password:`. The variable is retained only so the path can be re-enabled once Cassandra 6.0+ becomes a supported target. Keep JKS passwords out of source control with Ansible Vault instead.

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

## Example: Cassandra 3.11

Cassandra 3.11 requires Java 8 and uses the legacy `cassandra.yaml` schema.
The role picks the right template directory (`templates/3.11.x/`), variable
set (`vars/cassandra-3.11.yml`) and config file list (single `jvm.options`)
automatically when `cassandra_version` starts with `3.11`.

```yaml
- hosts: cassandra
  become: true
  vars:
    cassandra_version: 3.11.17
    cassandra_cluster_name: legacy-cluster
    cassandra_dc: dc1
    cassandra_rack: rack1
    cassandra_max_heap_size: 4G
    cassandra_seeds: "{{ groups['cassandra'] | map('extract', hostvars, ['ansible_default_ipv4', 'address']) | list | join(',') }}"
  roles:
    - role: axonops.axonops.java
      # No need to set java_zulu_version — the java role detects 3.11 → Java 8.
    - role: axonops.axonops.cassandra
```

A full working example lives at [`examples/cassandra-3.11.yml`](../../examples/cassandra-3.11.yml).
