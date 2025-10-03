# AxonOps Ansible Collection Examples

This directory contains example playbooks demonstrating how to use the AxonOps Ansible Collection to deploy and manage Apache Cassandra clusters with AxonOps monitoring.

## Available Examples

### Agent Deployment

#### [axon-agent.yml](axon-agent.yml)
Deploys AxonOps Agent alongside Apache Cassandra on target hosts.

**Features:**
- Installs Java 11
- Deploys Apache Cassandra 4.1
- Configures AxonOps Agent with Cassandra 4.1 agent
- Connects to AxonOps Server or SaaS

**Key Variables:**
- `axon_agent_version`: AxonOps Agent version (default: 2.0.2)
- `axon_java_agent`: Java agent package (e.g., `axon-cassandra4.1-agent`)
- `axon_agent_server_host`: AxonOps Server endpoint
- `axon_agent_customer_name`: Organization identifier
- `install_cassandra`: Set to `false` if Cassandra is already installed

### Server Deployment

#### [axon-server.yml](axon-server.yml)
Deploys a complete AxonOps Server stack including Cassandra, Elasticsearch, and the AxonOps Dashboard.

**Components:**
- Apache Cassandra 5.0 (metadata storage)
- Elasticsearch 7.x (metrics storage)
- AxonOps Server (API and backend)
- AxonOps Dashboard (web UI)
- AxonOps Agent (monitoring the local Cassandra)

**Key Variables:**
- `axon_server_cql_hosts`: Cassandra connection endpoints
- `axon_dash_listen_address`: Dashboard bind address
- `axon_server_elastic_host`: Elasticsearch endpoint (legacy)
- `axon_server_elastic_hosts`: Elasticsearch endpoints (server >= 2.0.4)

### Cassandra Deployments

#### [cassandra-4.1.yml](cassandra-4.1.yml)
Deploys Apache Cassandra 4.1 with AxonOps Agent.

**Features:**
- Apache Cassandra 4.1.9
- Multi-node cluster support with seed configuration
- AxonOps Agent with Cassandra 4.1 integration

**Key Variables:**
- `cassandra_version`: Specific Cassandra version
- `cassandra_seeds`: Comma-separated list of seed nodes
- `cassandra_cluster_name`: Cluster identifier

#### [cassandra-5.0.yml](cassandra-5.0.yml)
Deploys Apache Cassandra 5.0 with AxonOps Agent (requires JDK 17).

**Features:**
- Apache Cassandra 5.0
- JDK 17 support
- AxonOps Agent with Cassandra 5.0 integration

**Key Variables:**
- `java_pkg`: Java package (e.g., `openjdk-17-jre-headless`)
- `axon_java_agent`: Use `axon-cassandra5.0-agent-jdk17`

### Operations

#### [cassandra-rolling-start.yml](cassandra-rolling-start.yml)
Performs rolling start or restart of Cassandra nodes and AxonOps Agent.

**Features:**
- Serial execution (one node at a time)
- Waits for Cassandra to be fully operational before proceeding
- Useful for cluster-wide restarts without downtime

**Usage:**
```bash
# Start services
ansible-playbook -i inventory cassandra-rolling-start.yml

# Restart services
ansible-playbook -i inventory cassandra-rolling-start.yml -e "state=restarted"
```

## Prerequisites

1. **Ansible installed** on your control machine (version 2.10+)
2. **SSH access** to target hosts with sudo privileges
3. **Inventory file** defining your host groups:
   - `cassandra`: Hosts for Cassandra nodes
   - `axon-server`: Hosts for AxonOps Server
4. **Network connectivity** between nodes for Cassandra cluster formation

## Quick Start

### 1. Install the Collection

```bash
ansible-galaxy collection install axonops.axonops
```

### 2. Create an Inventory File

```ini
[cassandra]
cassandra1 ansible_host=192.168.1.10
cassandra2 ansible_host=192.168.1.11
cassandra3 ansible_host=192.168.1.12

[axon-server]
axon-server1 ansible_host=192.168.1.20
```

### 3. Deploy AxonOps Server

```bash
ansible-playbook -i inventory examples/axon-server.yml
```

### 4. Deploy Cassandra with AxonOps Agent

```bash
ansible-playbook -i inventory examples/cassandra-4.1.yml
```

## Common Configuration Patterns

### Using AxonOps SaaS

Leave `axon_agent_server_host` empty or set it to the default SaaS endpoint:

```yaml
vars:
  axon_agent_server_host: ""  # Uses agents.axonops.cloud
  axon_agent_customer_name: "your-company-name"
```

### Using Self-Hosted AxonOps Server

Point agents to your AxonOps Server:

```yaml
vars:
  axon_agent_server_host: "{{ groups['axon-server'] | first }}"
  axon_agent_tls_mode: "disabled"  # or "TLS" for production
```

### Multi-DC Cassandra Cluster

Configure datacenter and rack topology:

```yaml
vars:
  cassandra_cluster_name: production
  cassandra_dc: dc1
  cassandra_rack: rack1
  cassandra_endpoint_snitch: GossipingPropertyFileSnitch
```

### Custom Cassandra Configuration

Override defaults from [roles/cassandra/defaults/main.yml](../roles/cassandra/defaults/main.yml):

```yaml
vars:
  cassandra_version: 4.1.9
  cassandra_max_heap_size: 8G
  cassandra_concurrent_reads: 64
  cassandra_concurrent_writes: 64
  cassandra_num_tokens: 256
```

## Important Notes

### Firewall Configuration

The examples disable `firewalld` for demonstration purposes. In production:

1. Remove the firewall disable task
2. Configure proper firewall rules for:
   - Cassandra: 7000 (storage), 7001 (SSL), 9042 (CQL), 7199 (JMX)
   - AxonOps Server: 1888 (agent connections), 8080 (API)
   - AxonOps Dashboard: 3000 (web UI)
   - Elasticsearch: 9200 (HTTP), 9300 (transport)

### TLS Configuration

For production deployments, enable TLS:

```yaml
vars:
  axon_agent_tls_mode: "TLS"
  cassandra_ssl_internode_encryption: "all"
  cassandra_ssl_client_encryption_enabled: true
```

### Version Compatibility

| Cassandra Version | Java Version | AxonOps Agent Package |
|-------------------|--------------|----------------------|
| 3.11.x           | Java 8       | axon-cassandra3.11-agent |
| 4.0.x            | Java 8/11    | axon-cassandra4.0-agent |
| 4.1.x            | Java 8/11    | axon-cassandra4.1-agent |
| 5.0.x            | Java 11/17   | axon-cassandra5.0-agent-jdk17 |

## Troubleshooting

### Check Service Status

```bash
ansible cassandra -i inventory -m shell -a "systemctl status cassandra axon-agent"
```

### View Logs

```bash
# Cassandra logs
tail -f /var/log/cassandra/system.log

# AxonOps Agent logs
journalctl -u axon-agent -f

# AxonOps Server logs
journalctl -u axon-server -f
```

### Verify Agent Connectivity

Check if agents are connecting to the server:

```bash
curl http://localhost:8080/api/v1/agents
```

## Additional Resources

- [AxonOps Documentation](https://docs.axonops.com/)
- [Role Defaults](../roles/)
- [Apache Cassandra Documentation](https://cassandra.apache.org/doc/)

## Support

For issues or questions:
- GitHub Issues: https://github.com/axonops/axonops-ansible-collection/issues
- AxonOps Support: support@axonops.com
