# Elasticsearch Role

## Overview

The `elastic` role installs and configures Elasticsearch for use with AxonOps Server. AxonOps uses Elasticsearch to store configuration data, user settings, and other operational metadata.

**Note**: This role is based on the official [elastic.elasticsearch](https://galaxy.ansible.com/elastic/elasticsearch/) Ansible role and supports Elasticsearch versions 6.x, 7.x, and 8.x (with limitations).

## Requirements

- Ansible 2.9 or higher
- Target system running a supported Linux distribution
- Sufficient system resources for Elasticsearch
- `jmespath` library on the Ansible control machine (required for json_query filter)

## Important Version Information

- **Primary Support**: 7.x and 6.x
- **8.x Support**: Should work with 8.x but with limited testing. See [8x-support documentation](https://github.com/elastic/ansible-elasticsearch/blob/main/docs/8x-support.md)
- **OSS Distribution**: No longer available for versions >= 7.11.0 due to Elasticsearch license changes

## Role Variables

### Basic Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `es_version` | `7.17.0` | Version of Elasticsearch to install |
| `es_use_repository` | `true` | Use official Elastic package repositories |
| `es_add_repository` | `true` | Add Elastic repositories (if not already present) |
| `oss_version` | `false` | Install OSS distribution (only for versions < 7.11.0) |

### Network Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `es_config['http.port']` | `9200` | HTTP port for the node |
| `es_config['transport.port']` | `9300` | Transport port for the node |
| `es_config['network.host']` | - | Sets both bind and publish host |
| `es_api_host` | `localhost` | Host for HTTP API calls |
| `es_api_port` | `9200` | Port for HTTP API calls |

### Cluster Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `es_config['cluster.name']` | - | Name of the Elasticsearch cluster |
| `es_config['node.name']` | - | Name of the node |
| `es_config['discovery.seed_hosts']` | - | List of master-eligible nodes for discovery |
| `es_config['cluster.initial_master_nodes']` | - | Initial master nodes for cluster bootstrap (7.x+) |

### Node Roles

| Variable | Default | Description |
|----------|---------|-------------|
| `es_config['node.master']` | - | Whether this node can be elected as master |
| `es_config['node.data']` | - | Whether this node stores data |

### Memory and Performance

| Variable | Default | Description |
|----------|---------|-------------|
| `es_heap_size` | - | JVM heap size (e.g., "1g", "4g") |
| `es_config['bootstrap.memory_lock']` | - | Lock process memory to prevent swapping |

### Data and Log Directories

| Variable | Default | Description |
|----------|---------|-------------|
| `es_data_dirs` | - | Array of data directory paths |
| `es_log_dir` | - | Log directory path |

### Security (X-Pack)

| Variable | Default | Description |
|----------|---------|-------------|
| `es_xpack_trial` | `false` | Enable 30-day X-Pack trial |
| `es_api_basic_auth_username` | - | Admin username for API calls |
| `es_api_basic_auth_password` | - | Admin password for API calls |
| `es_xpack_license` | - | X-Pack license JSON content |

### Plugins

| Variable | Default | Description |
|----------|---------|-------------|
| `es_plugins` | - | Array of plugins to install |
| `es_plugins_reinstall` | `false` | Reinstall all plugins |

## Dependencies

None (Java installation is handled by the role)

## Example Playbooks

### Simple Single Node for AxonOps

```yaml
- name: Install Elasticsearch for AxonOps
  hosts: axon-server
  become: true
  vars:
    es_version: 7.17.0

  roles:
    - role: axonops.axonops.elastic
```

### AxonOps Server with Custom Elasticsearch Configuration

```yaml
- name: Install Elasticsearch with Custom Configuration
  hosts: axon-server
  become: true
  vars:
    es_version: 7.17.0
    es_heap_size: 2g
    es_data_dirs:
      - /opt/elasticsearch/data
    es_log_dir: /opt/elasticsearch/logs
    es_config:
      node.name: "axonops-node1"
      cluster.name: "axonops-cluster"
      network.host: 0.0.0.0
      http.port: 9200
      bootstrap.memory_lock: true

  roles:
    - role: axonops.axonops.elastic
```

### Complete AxonOps Server Stack

```yaml
- name: Deploy AxonOps Server
  hosts: axon-server
  become: true
  vars:
    install_cassandra: true
    install_elastic: true
    java_pkg: java-17-openjdk-headless

    # Elasticsearch Configuration
    es_version: 7.17.0
    es_heap_size: 2g
    es_config:
      cluster.name: "axonops"
      node.name: "{{ ansible_hostname }}"
      network.host: 0.0.0.0
      http.port: 9200
      discovery.type: single-node

    # AxonOps Server Configuration
    axon_server_elastic_hosts:
      - http://127.0.0.1:9200
    axon_server_cql_hosts:
      - localhost:9042
    axon_dash_listen_address: 0.0.0.0

  roles:
    - role: axonops.axonops.elastic
      tags: elastic
      when: install_elastic

    - role: axonops.axonops.cassandra
      tags: cassandra
      when: install_cassandra

    - role: axonops.axonops.server
      tags: server

    - role: axonops.axonops.dash
      tags: dash
```

### Multi-Node Elasticsearch Cluster

```yaml
- hosts: elastic_master
  become: true
  roles:
    - role: axonops.axonops.elastic
  vars:
    es_version: 7.17.0
    es_heap_size: 4g
    es_config:
      cluster.name: "axonops-production"
      cluster.initial_master_nodes: "master-node-1"
      discovery.seed_hosts: "master-node-1:9300"
      node.name: "master-node-1"
      node.master: true
      node.data: false
      network.host: 0.0.0.0
      http.port: 9200
      transport.port: 9300
      bootstrap.memory_lock: true

- hosts: elastic_data
  become: true
  roles:
    - role: axonops.axonops.elastic
  vars:
    es_version: 7.17.0
    es_heap_size: 8g
    es_data_dirs:
      - /opt/elasticsearch/data
    es_config:
      cluster.name: "axonops-production"
      discovery.seed_hosts: "master-node-1:9300"
      node.name: "{{ ansible_hostname }}"
      node.master: false
      node.data: true
      network.host: 0.0.0.0
      http.port: 9200
      transport.port: 9300
      bootstrap.memory_lock: true
```

### Elasticsearch with Plugins

```yaml
- name: Install Elasticsearch with Plugins
  hosts: axon-server
  become: true
  vars:
    es_version: 7.17.0
    es_plugins:
      - plugin: ingest-attachment

  roles:
    - role: axonops.axonops.elastic
```

### Using Custom Package URL

```yaml
- name: Install Elasticsearch from Custom URL
  hosts: axon-server
  become: true
  vars:
    es_version: 7.17.0
    es_use_repository: false
    es_custom_package_url: https://downloads.example.com/elasticsearch-7.17.0.rpm

  roles:
    - role: axonops.axonops.elastic
```

## Configuration for AxonOps Server Versions

### AxonOps Server >= 2.0.4

For AxonOps Server version 2.0.4 and above, use the new `hosts` array format:

```yaml
axon_server_elastic_hosts:
  - http://127.0.0.1:9200
```

### AxonOps Server < 2.0.4

For older server versions, use the legacy configuration:

```yaml
axon_server_elastic_host: "http://127.0.0.1"
axon_server_elastic_port: "9200"
```

## Important Notes

### Memory Configuration

- **Heap Size**: Set `es_heap_size` to about 50% of available RAM, but not more than 31GB
- **Memory Lock**: Enable `bootstrap.memory_lock` to prevent swapping

### Network Configuration

- **Important**: If Elasticsearch binds to a different host or port than the defaults, update `es_api_host` and `es_api_port`
- The role uses these variables for HTTP operations like installing templates and checking node status

### Directory Configuration

- **Do not use both**: Use `es_data_dirs` and `es_log_dir` OR `es_config['path.data']` and `es_config['path.logs']`, not both
- Using both will create duplicate entries in `elasticsearch.yml` and cause startup failures

### Plugin Management

- Plugins are automatically managed based on the Elasticsearch version
- Setting `es_plugins_reinstall: true` will remove and reinstall all plugins
- If `es_plugins` is empty, all currently installed plugins will be removed

### Service Management

| Variable | Default | Description |
|----------|---------|-------------|
| `es_start_service` | `true` | Whether to start Elasticsearch after installation |
| `es_restart_on_change` | `true` | Whether to restart Elasticsearch when configuration changes |

## Tags

Available tags for granular control (use `--list-tasks` to see all available tags):
- Standard Ansible role tags for different installation phases

## Additional Configuration Files

You can override default configuration templates:

```yaml
es_config_default: "my-elasticsearch.j2"      # Override /etc/default/elasticsearch
es_config_jvm: "my-jvm.options.j2"            # Override jvm.options
es_config_log4j2: "my-log4j2.properties.j2"   # Override log4j2.properties
```

## Proxy Configuration

For environments requiring proxy access:

```yaml
es_proxy_host: proxy.example.com
es_proxy_port: 8080
```

## License

See the main collection LICENSE file and the [Elasticsearch role LICENSE](https://github.com/elastic/ansible-elasticsearch/blob/main/LICENSE).

## Author

Originally by Elastic
Integrated by AxonOps Limited

## Additional Resources

- [Elastic Ansible Role Documentation](https://github.com/elastic/ansible-elasticsearch)
- [Elasticsearch Documentation](https://www.elastic.co/guide/en/elasticsearch/reference/current/index.html)
