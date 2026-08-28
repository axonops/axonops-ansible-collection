# Self-Hosted Example

This directory contains a minimal set of playbooks and inventories for deploying a self-hosted AxonOps stack. The stack consists of:

- **Apache Cassandra** — metrics and configuration storage for AxonOps Server
- **Search backend** — OpenSearch (preferred) or Elasticsearch (legacy/existing deployments)
- **AxonOps Server** — the core monitoring backend
- **AxonOps Dashboard** — the web UI

## Inventory Groups

All playbooks and inventories in this directory use the same three group names. Keep them consistent — the seed and host lists are derived from `groups[...]`, so a renamed group breaks the plays.

| Group | Contents |
|-------|----------|
| `axonops_server` | The AxonOps Server and Dashboard host |
| `axonops_searchdb` | The OpenSearch or Elasticsearch nodes |
| `axonops_cassandra` | The Cassandra nodes AxonOps writes metrics to |

## Search Backend Options

### OpenSearch (recommended for on-premises)

OpenSearch is the preferred search backend for new on-premises deployments. It is actively maintained as a fully open-source project, includes the Security plugin out of the box, and generates TLS certificates automatically.

Use these files when deploying with OpenSearch:

| File | Purpose |
|------|---------|
| `axon-search-opensearch.yml` | Installs and configures OpenSearch on `axonops_searchdb` hosts |
| `axon-server.yml` | Installs AxonOps Server and Dashboard on `axonops_server` hosts |
| `inventories/axonops-opensearch.yml` | Inventory with multi-node OpenSearch cluster and AxonOps Server connection settings |

### Elasticsearch (legacy / existing deployments)

Use Elasticsearch if you have an existing installation or are migrating from an older AxonOps deployment.

| File | Purpose |
|------|---------|
| `axon-search.yml` | Installs and configures Elasticsearch on `axonops_searchdb` hosts |
| `axon-server.yml` | Installs AxonOps Server and Dashboard on `axonops_server` hosts |
| `inventories/axonops.yml` | Inventory with multi-node Elasticsearch cluster and AxonOps Server connection settings |

## Playbook Descriptions

### `axon-search-opensearch.yml`

Deploys OpenSearch on nodes in the `axonops_searchdb` inventory group. The `opensearch` role handles:

- Downloading and installing OpenSearch
- Generating TLS certificates using the searchguard-tlstool
- Configuring the Security plugin and setting the admin password
- Applying kernel tuning (vm.max_map_count, THP, memory lock)
- Starting and enabling the OpenSearch systemd service

No Java installation is required — OpenSearch ships with a bundled JDK.

### `axon-search.yml`

Deploys Elasticsearch on nodes in the `axonops_searchdb` inventory group. Java must be installed separately (included in the playbook via the `java` role).

### `axon-server.yml`

Deploys AxonOps Server and AxonOps Dashboard on nodes in the `axonops_server` inventory group. The search backend (OpenSearch or Elasticsearch) must be running before this playbook runs.

### `axon-cassandra.yml`

Deploys Apache Cassandra and the AxonOps Agent on nodes in the `axonops_cassandra` inventory group. Cassandra serves as the time-series metrics store for AxonOps Server. Use it with `inventories/cassandra.yml`, which holds all Cassandra and agent variables.

### `cassandra-5.0.yml`

A standalone Cassandra 5.0 + AxonOps Agent example, including the `preflight` role and pinned agent versions. It targets the `axonops_cassandra` group by default; override with `-e target=<group>`. Unlike `axon-cassandra.yml`, it carries its variables in the playbook itself, so it can be used with any inventory that defines `axonops_cassandra` and `axonops_server`.

## Quick Start: OpenSearch Deployment

### 1. Configure the inventory

Copy `inventories/axonops-opensearch.yml` and replace the placeholder IP addresses with your own. The example uses a three-node OpenSearch cluster with AxonOps Server on the first node.

Set `axon_server_org_name` — the `server` role fails without it — and a strong admin password. In production, store the password in Ansible Vault:

```bash
ansible-vault encrypt_string 'MyStr0ngP@ssword' --name 'opensearch_admin_password'
```

Paste the output into your inventory under `vars`.

### 2. Deploy OpenSearch

```bash
ansible-playbook -i inventories/axonops-opensearch.yml axon-search-opensearch.yml
```

### 3. Deploy Cassandra

AxonOps Server needs Cassandra for metrics storage, so deploy it before the server:

```bash
ansible-playbook -i inventories/cassandra.yml axon-cassandra.yml
```

Then set `axon_server_cql_hosts` in `inventories/axonops-opensearch.yml` to those Cassandra nodes.

### 4. Deploy AxonOps Server and Dashboard

```bash
ansible-playbook -i inventories/axonops-opensearch.yml axon-server.yml
```

### 5. Open the Dashboard

The dashboard listens on `axon_dash_listen_address:axon_dash_listen_port`, which the example inventories set to `0.0.0.0:3000`:

```
http://<axonops_server-ip>:3000
```

The role default is `127.0.0.1`, which is only reachable from the server itself. For a production deployment put the dashboard behind TLS using `axon_dash_nginx`.

## Quick Start: Elasticsearch Deployment

Same sequence, with `inventories/axonops.yml` and `axon-search.yml`:

```bash
ansible-playbook -i inventories/axonops.yml       axon-search.yml
ansible-playbook -i inventories/cassandra.yml     axon-cassandra.yml
ansible-playbook -i inventories/axonops.yml       axon-server.yml
```

## Inventory Reference

### `inventories/axonops-opensearch.yml`

Defines a three-node OpenSearch cluster (`axonops_searchdb`) and a single AxonOps Server node (`axonops_server`).

OpenSearch cluster variables, set on `axonops_searchdb`:

| Variable | Description |
|----------|-------------|
| `opensearch_cluster_name` | OpenSearch cluster name. Change this for every deployment |
| `opensearch_cluster_type` | `single-node` or `multi-node` |
| `opensearch_heap_size` | JVM heap size (e.g. `2g`). Set to no more than half available RAM |
| `opensearch_domain_name` | Domain name used in generated TLS certificate DNs |
| `opensearch_admin_password` | Password for the built-in `admin` user. Use Ansible Vault in production |

AxonOps Server variables, set on `axonops_server`:

| Variable | Description |
|----------|-------------|
| `axon_server_org_name` | **Required.** Organisation name. Must match `axon_agent_customer_name` on the Cassandra nodes |
| `axon_server_searchdb_hosts` | List of OpenSearch API URLs, derived from the `axonops_searchdb` group. Use `https://` with the Security plugin enabled |
| `axon_server_searchdb_username` | Username for AxonOps Server to connect to OpenSearch (typically `admin`) |
| `axon_server_searchdb_password` | Must match `opensearch_admin_password` |
| `axon_server_searchdb_tls_skip_verify` | Set to `true` when using auto-generated self-signed certificates |
| `axon_server_cql_hosts` | List of `host:port` Cassandra contact points for the metrics store |
| `axon_server_username` / `axon_server_password` | Cassandra credentials |
| `axon_server_local_dc` | Cassandra datacentre name. Must match `cassandra_dc` |
| `axon_dash_listen_address` / `axon_dash_listen_port` | Dashboard bind address and port |

These server-side variables belong on the `axonops_server` group, not on `axonops_searchdb` — the `server` role only runs on `axonops_server`.

### `inventories/axonops.yml`

Same layout, with Elasticsearch instead of OpenSearch. All three Elasticsearch nodes are master-eligible and hold data, so the cluster keeps a quorum (2 of 3) if one node is lost. `discovery.seed_hosts` and `cluster.initial_master_nodes` are derived from the `axonops_searchdb` group so they cannot drift out of sync with the host list.

### `inventories/cassandra.yml`

Defines the `axonops_cassandra` nodes plus an `axonops_server` group so agents know where to report. Key variables:

| Variable | Description |
|----------|-------------|
| `cassandra_cluster_name` | Cassandra cluster name |
| `cassandra_dc` / `cassandra_rack` | Topology. `cassandra_dc` must match `axon_server_local_dc` |
| `cassandra_seeds` | Derived from the `axonops_cassandra` group |
| `axon_agent_server_host` | Derived from the `axonops_server` group. Leave empty to use the SaaS environment |
| `axon_agent_customer_name` | Must match `axon_server_org_name` on the AxonOps Server |
| `axon_java_agent` | Agent JAR matching your Cassandra and JDK version |

## AxonOps Server Version Compatibility

The search backend connection format changed in AxonOps Server 2.0.4:

- **Version >= 2.0.4** (current): Uses `search_db.hosts` — a list of full URLs. Set `axon_server_searchdb_hosts` to a list of URLs.
- **Version < 2.0.4** (legacy): Uses `elastic_host` and `elastic_port` as separate top-level keys.

The `server` role detects the version automatically and writes the correct format.

## Security Notes

- **Never commit passwords in plain text.** Use [Ansible Vault](https://docs.ansible.com/ansible/latest/vault_guide/) to encrypt sensitive values. This applies to `opensearch_admin_password`, `axon_server_searchdb_password`, and `axon_server_password`.
- **The `firewalld` stop task** in each playbook is included only so the examples work without additional firewall configuration. Remove it in production and configure proper rules instead.
- **TLS skip verify** (`axon_server_searchdb_tls_skip_verify: true`) is acceptable when using auto-generated self-signed certificates in a trusted private network. For production, supply certificates from a trusted CA using `opensearch_tls_mode: custom` and set `skip_verify` to `false`.
- **The dashboard binds to `0.0.0.0` in these examples.** Put it behind TLS with `axon_dash_nginx` before exposing it.

## Related Documentation

- [OpenSearch role documentation](../../docs/roles/opensearch.md)
- [Elasticsearch role documentation](../../docs/roles/elastic.md)
- [AxonOps Server role documentation](../../docs/roles/server.md)
- [Role documentation index](../../docs/roles/README.md)
