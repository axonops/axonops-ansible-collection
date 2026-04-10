# Self-Hosted Example

This directory contains a minimal set of playbooks and inventories for deploying a self-hosted AxonOps stack. The stack consists of:

- **Apache Cassandra** — metrics and configuration storage for AxonOps Server
- **Search backend** — OpenSearch (preferred) or Elasticsearch (legacy/existing deployments)
- **AxonOps Server** — the core monitoring backend
- **AxonOps Dashboard** — the web UI

## Search Backend Options

### OpenSearch (recommended for on-premises)

OpenSearch is the preferred search backend for new on-premises deployments. It is actively maintained as a fully open-source project, includes the Security plugin out of the box, and generates TLS certificates automatically.

Use these files when deploying with OpenSearch:

| File | Purpose |
|------|---------|
| `axon-search-opensearch.yml` | Installs and configures OpenSearch on `axonops-searchdb` hosts |
| `axon-server.yml` | Installs AxonOps Server and Dashboard on `axonops-server` hosts |
| `inventories/axonops-opensearch.yml` | Inventory with multi-node OpenSearch cluster and AxonOps Server connection settings |

### Elasticsearch (legacy / existing deployments)

Use Elasticsearch if you have an existing installation or are migrating from an older AxonOps deployment.

| File | Purpose |
|------|---------|
| `axon-search.yml` | Installs and configures Elasticsearch on `axonops-searchdb` hosts |
| `axon-server.yml` | Installs AxonOps Server and Dashboard on `axonops-server` hosts |
| `inventories/axonops.yml` | Inventory with multi-node Elasticsearch cluster and AxonOps Server connection settings |

## Playbook Descriptions

### `axon-search-opensearch.yml`

Deploys OpenSearch on nodes in the `axonops-searchdb` inventory group. The `opensearch` role handles:

- Downloading and installing OpenSearch
- Generating TLS certificates using the searchguard-tlstool
- Configuring the Security plugin and setting the admin password
- Applying kernel tuning (vm.max_map_count, THP, memory lock)
- Starting and enabling the OpenSearch systemd service

No Java installation is required — OpenSearch ships with a bundled JDK.

### `axon-search.yml`

Deploys Elasticsearch on nodes in the `axonops-searchdb` inventory group. Java must be installed separately (included in the playbook via the `java` role).

### `axon-server.yml`

Deploys AxonOps Server and AxonOps Dashboard on nodes in the `axonops-server` inventory group. The search backend (OpenSearch or Elasticsearch) must be running before this playbook runs.

### `axon-cassandra.yml`

Deploys Apache Cassandra with the AxonOps Agent on nodes in the `axonops-cassandra` inventory group. Cassandra serves as the time-series metrics store for AxonOps Server.

## Quick Start: OpenSearch Deployment

### 1. Configure the inventory

Copy `inventories/axonops-opensearch.yml` and replace the placeholder IP addresses with your own. The example uses a three-node OpenSearch cluster with AxonOps Server on the first node.

Set a strong admin password. In production, store it in Ansible Vault:

```bash
ansible-vault encrypt_string 'MyStr0ngP@ssword' --name 'opensearch_admin_password'
```

Paste the output into your inventory under `vars`.

### 2. Deploy OpenSearch

```bash
ansible-playbook -i inventories/axonops-opensearch.yml axon-search-opensearch.yml
```

### 3. Deploy AxonOps Server

```bash
ansible-playbook -i inventories/axonops-opensearch.yml axon-server.yml
```

### 4. Deploy Cassandra (optional)

If you need a local Cassandra cluster for AxonOps metrics storage:

```bash
ansible-playbook -i inventories/axonops-opensearch.yml axon-cassandra.yml
```

## Quick Start: Elasticsearch Deployment

### 1. Configure the inventory

Copy `inventories/axonops.yml` and replace the placeholder IP addresses with your own.

### 2. Deploy Elasticsearch

```bash
ansible-playbook -i inventories/axonops.yml axon-search.yml
```

### 3. Deploy AxonOps Server

```bash
ansible-playbook -i inventories/axonops.yml axon-server.yml
```

## Inventory Reference

### `inventories/axonops-opensearch.yml`

Defines a three-node OpenSearch cluster (`axonops-searchdb`) and a single AxonOps Server node (`axonops-server`).

Key variables:

| Variable | Description |
|----------|-------------|
| `opensearch_cluster_name` | OpenSearch cluster name. Change this for every deployment |
| `opensearch_cluster_type` | `single-node` or `multi-node` |
| `opensearch_heap_size` | JVM heap size (e.g. `2g`). Set to no more than half available RAM |
| `opensearch_domain_name` | Domain name used in generated TLS certificate DNs |
| `opensearch_admin_password` | Password for the built-in `admin` user. Use Ansible Vault in production |
| `axon_server_searchdb_hosts` | List of OpenSearch API URLs. Use `https://` with the Security plugin enabled |
| `axon_server_searchdb_username` | Username for AxonOps Server to connect to OpenSearch (typically `admin`) |
| `axon_server_searchdb_password` | Must match `opensearch_admin_password` |
| `axon_server_searchdb_tls_skip_verify` | Set to `true` when using auto-generated self-signed certificates |

### `inventories/axonops.yml`

Defines a three-node Elasticsearch cluster (`axonops-searchdb`) and a single AxonOps Server node (`axonops-server`). Elasticsearch node configuration is provided per-host via `es_config`.

## AxonOps Server Version Compatibility

The search backend connection format changed in AxonOps Server 2.0.4:

- **Version >= 2.0.4** (current): Uses `search_db.hosts` — a list of full URLs. Set `axon_server_searchdb_hosts` to a list of URLs.
- **Version < 2.0.4** (legacy): Uses `elastic_host` and `elastic_port` as separate top-level keys.

The `server` role detects the version automatically and writes the correct format.

## Security Notes

- **Never commit passwords in plain text.** Use [Ansible Vault](https://docs.ansible.com/ansible/latest/vault_guide/) to encrypt sensitive values.
- **The `firewalld` stop task** in each playbook is included only so the examples work without additional firewall configuration. Remove it in production and configure proper rules instead.
- **TLS skip verify** (`axon_server_searchdb_tls_skip_verify: true`) is acceptable when using auto-generated self-signed certificates in a trusted private network. For production, supply certificates from a trusted CA using `opensearch_tls_mode: custom` and set `skip_verify` to `false`.

## Related Documentation

- [OpenSearch role documentation](../../docs/roles/opensearch.md)
- [Elasticsearch role documentation](../../docs/roles/elastic.md)
- [AxonOps Server role documentation](../../docs/roles/server.md)
- [Role documentation index](../../docs/roles/README.md)
