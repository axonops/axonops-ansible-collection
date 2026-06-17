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

### Service control

| Variable | Default | Effect |
|----------|---------|--------|
| `cassandra_start_on_install` | `false` | When `false`, the role installs and (per `cassandra_start_on_boot`) enables the `cassandra` service but does **not** start it on first install — the node is left for an external operator to bootstrap. When `true`, the role starts the service. A node that is already running is always (re)started so a config change takes effect, regardless of this flag. |
| `cassandra_start_on_boot` | `false` | Controls boot-time enablement only (`systemctl enable`). Independent of `cassandra_start_on_install` — enabling at boot does not start the node during the play. |

## cqlsh on modern Python (3.12+)

The `cqlsh` shipped with Apache Cassandra relies on a Python driver that imports
stdlib modules removed in Python 3.12 (e.g. `asyncore`, `imp`). On distributions
whose **system Python is 3.12 or newer — notably Ubuntu 24.04 and Debian 13** —
the bundled `cqlsh` aborts at startup with an import error. Older distros (Rocky
Linux 9, Ubuntu 22.04, Debian 12) ship Python 3.9–3.11 and are unaffected.

To make `cqlsh` work everywhere, the role provisions a dedicated Python virtual
environment containing the maintained standalone [`cqlsh`](https://pypi.org/project/cqlsh/)
package (which supports modern Python) and installs a wrapper that launches it.
The system Python and the distribution's own `cqlsh` are left untouched.

By default the wrapper is installed as `/usr/local/bin/cqlsh`, which **shadows**
the broken distribution `cqlsh` on the `PATH` (`/usr/local/bin` precedes the
tar install's `bin/` directory), so the plain command just works:

```bash
cqlsh <host> <port>
```

To install the wrapper side-by-side instead of shadowing, set
`cassandra_cqlsh_wrapper_path: /usr/local/bin/cqlsh-venv` and invoke it
explicitly:

```bash
cqlsh-venv <host> <port>
```

| Variable | Type | Default | Purpose |
|----------|------|---------|---------|
| `cassandra_cqlsh_venv_enabled` | bool | `true` | Provision the cqlsh venv and wrapper. Set `false` to skip entirely. |
| `cassandra_cqlsh_venv_path` | string | `/opt/cassandra-cqlsh-venv` | Absolute path of the virtual environment. |
| `cassandra_cqlsh_python` | string | `python3` | Target-host interpreter used to create the venv. The target's own `python3` is fine — the standalone `cqlsh` package supports Python 3.12+. |
| `cassandra_cqlsh_venv_packages` | list | `[cqlsh]` | Packages installed into the venv. `cqlsh` pulls in a compatible driver. Pin a version (e.g. `[cqlsh==6.2.0]`) for reproducible installs. |
| `cassandra_cqlsh_wrapper_path` | string | `/usr/local/bin/cqlsh` | Path of the wrapper script that execs cqlsh from the venv. Defaults to shadowing the distribution `cqlsh` on `PATH`. |

Set `cassandra_cqlsh_venv_enabled: false` on distributions whose Python is 3.11
or earlier (where the bundled cqlsh already works), or in air-gapped
environments without a PyPI mirror.

> **Note:** provisioning the venv installs `cqlsh` from PyPI, so the **target
> host** needs network access (or an internal PyPI mirror) at provision time.
> The venv is built with the target host's own `python3`; no additional Python
> version is required.

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

## Upgrade Notes

### 0.6.0 — `cassandra_data_directory` default changed (breaking)

`cassandra_data_directory` now defaults to `/var/lib/cassandra/data` (previously
`/var/lib/cassandra`). New installs are unaffected.

For an **existing** cluster that relied on the old default, the data path moves,
so Cassandra would start against an empty directory. The role refuses to run in
that situation: a preflight guard fails the play when `cassandra_data_directory`
contains no `system` keyspace directory while its parent does (i.e. data is
still laid out under the old default). The guard can be disabled with
`cassandra_data_directory_check: false` once the data location is confirmed.

Migrate **one node at a time**, confirming the node is back to `UN` in
`nodetool status` before moving to the next:

1. Flush memtables and stop accepting writes: `nodetool drain`.
2. Take a safety snapshot (cheap, hard links): `nodetool snapshot -t pre-datadir-move`.
   The snapshot lives inside each keyspace directory and moves with it.
3. Stop Cassandra on the node.
4. Create `/var/lib/cassandra/data` and move the existing keyspace directories
   into it. The keyspace directories are the top-level subdirectories of
   `/var/lib/cassandra` (`system/`, `system_schema/`, `system_auth/`,
   `system_distributed/`, `system_traces/`, and your application keyspaces).
   For example:

   ```bash
   mkdir /var/lib/cassandra/data
   cd /var/lib/cassandra
   mv system system_schema system_auth system_distributed system_traces <your_keyspaces> data/
   ```

   Do **not** move `commitlog/`, `hints/`, `saved_caches/`, `cdc_raw/`, or
   filesystem metadata such as `lost+found/`.
5. Fix ownership: `chown -R cassandra:cassandra /var/lib/cassandra/data`.
6. Start Cassandra and verify the node rejoins the ring (`nodetool status`
   shows `UN`), schema agreement holds (`nodetool describecluster` shows a
   single schema version), and existing tables are readable.
7. Only then proceed to the next node. Once the whole cluster is migrated,
   clear the snapshots: `nodetool clearsnapshot -t pre-datadir-move`.

To keep the previous behavior instead, pin the variable:

```yaml
cassandra_data_directory: /var/lib/cassandra
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
