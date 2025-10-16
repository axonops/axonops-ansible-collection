# AxonOps Ansible Collection

[AxonOps](https://axonops.com/) can be used either via our SaaS service or you can install it locally in your environment.

This collection provides Ansible roles and playbooks to deploy [AxonOps](https://axonops.com/) components. The examples below
show how you can install the AxonOps server with Elasticsearch® and Cassandra® to store metrics and configurations,
and how you can install the AxonOps agent to connect to your Apache Cassandra cluster.

Ansible is an open-source IT automation platform that enables organizations to automate various IT processes, including provisioning, configuration management,
application deployment, and orchestration. It operates as an agentless system, using remote connections via SSH or Windows Remote Management
to execute tasks. Ansible is widely used for its simplicity and flexibility, allowing users to define infrastructure as code.
For more information about Ansible, visit the [Ansible project documentation](https://docs.ansible.com/ansible/latest/index.html).

Although this example project has been implemented using Ansible, it is possible to achieve similar results using alternative tools like Chef or Puppet,
offering flexibility for those who prefer different automation solutions.

## Before you start

Apache Cassandra 5.0 introduced significant configuration changes that affect how you structure your Ansible playbooks. The most notable change is the shift from parameter names that include units to explicit unit declarations in values. For example:

```yaml
# Cassandra 4.1
dynamic_snitch_reset_interval_in_ms: 600000

# Cassandra 5.0
dynamic_snitch_reset_interval: 600000ms
```

This makes coding the ansible playbook to support both versions more complex. Before running this playbook, you'll need to review the variables from [roles/cassandra/defaults/main.yml](roles/cassandra/defaults/main.yml) and compare them against [roles/cassandra/templates/5.0.x/cassandra.yaml.j2](roles/cassandra/templates/5.0.x/cassandra.yaml.j2).

## Role Documentation

This collection provides the following Ansible roles. Click on each role for detailed documentation, configuration options, and examples:

### AxonOps Components
- **[agent](docs/roles/agent.md)** - Install and configure AxonOps Agent for Cassandra monitoring
- **[server](docs/roles/server.md)** - Install and configure AxonOps Server (self-hosted deployments)
- **[dash](docs/roles/dash.md)** - Install and configure AxonOps Dashboard web interface
- **[configurations](docs/roles/alerts.md)** - Configure alerts, integrations, and monitoring settings

### Infrastructure Components
- **[cassandra](docs/roles/cassandra.md)** - Install and configure Apache Cassandra (3.11, 4.x, 5.x)
- **[elastic](docs/roles/elastic.md)** - Install and configure Elasticsearch for AxonOps
- **[java](docs/roles/java.md)** - Install Java (OpenJDK or Azul Zulu)

### Utilities
- **[preflight](docs/roles/preflight.md)** - Run pre-installation system checks

For a complete guide including deployment patterns and quick references, see the [Role Documentation Index](docs/roles/README.md).

## Playbooks

### Installing the collection

Download the latest release from [GitHub](https://github.com/axonops/axonops-ansible-collection/releases/). Then use `ansible-galaxy`
to install the tarball into a directory configured in [COLLECTIONS_PATHS](https://docs.ansible.com/ansible/latest/reference_appendices/config.html#collections-paths).

```sh
ansible-galaxy collection install <downloaded_tar>
```

You may also use this short script to download and install the latest version:

```sh
LATEST=$(curl -s https://api.github.com/repos/axonops/axonops-ansible-collection/releases/latest | jq -r '.assets[0].browser_download_url')
ansible-galaxy collection install $LATEST
```

### Inventory

Before you can start using these playbooks you'll need to add your nodes to the inventory. You can find an example
in the [./examples](./examples) directory. There are two sections:

- axon-server: list here the IP address or hostname of the server where you would like to install AxonOps
- cassandra: these are the Apache Cassandra nodes where the agent will be installed

## Makefile Targets

The following targets are available in the Makefile:

- `help`: Display this help message.
- `agent`: Installs the AxonOps agent to the Cassandra nodes.
- `server`: Installs the AxonOps server with Elasticsearch and optional Cassandra.

You can then invoke the installation using

```sh
# the default SSH user is root but you can change it passing the ANSIBLE_USER variable
make agent ANSIBLE_USER=redhat
```

## Examples

### axon-agent.yml

This playbook deploys the AxonOps Agent to Cassandra nodes. If you do not need to install
Apache Cassandra, set the switch `install_cassandra` to false.

If you have a local mirror repositories of the AxonOps, Elastic and Cassandra packages adjust
the `*_redhat_repository` URLs.

```yaml
- name: Deploy AxonOps Agent
  hosts: cassandra
  become: true
  vars:
    axon_java_agent: "axon-cassandra4.1-agent"
    customer_name: example
    java_pkg: java-11-openjdk-headless
    # Set to false if you already have Apache Cassandra running
    install_cassandra: true

  roles:
    - role: cassandra
      tags: cassandra
      when: install_cassandra
      vars:
        cassandra_dc: "example"

    - role: agent
      tags: agent, axonops-agent
      vars:
        axon_agent_server_host: "{{ groups['axon-server'] | first }}"
        cassandra_dc: "DC1"
        cassandra_seeds: "{{ groups['cassandra'] | map('extract', hostvars, ['ansible_default_ipv4', 'address']) | list | first }}"
```

### axon-server.yml (note - you do not need to use this if connecting to the SaaS)

This playbook deploys the AxonOps Server. It installs a local Apache Cassandra server to use a metrics
storage and it will also deploy Elasticsearch for the AxonOps configuration.

For more information about the Elasticsearch installation options please see the following [README.md](./roles/elastic/README.md)

**Note:** For AxonOps server version >= 2.0.4, the Elasticsearch configuration uses a new syntax with a `hosts` array format.
The playbook automatically detects the server version and applies the appropriate configuration format. For older versions,
the legacy `elastic_host` and `elastic_port` configuration is used.

```yaml
- name: Deploy AxonOps Server
  hosts: axon-server
  become: true
  vars:
    install_cassandra: true
    install_elastic: true
    java_pkg: java-17-openjdk-headless
    axon_server_cql_hosts:
      - localhost:9042
    axon_dash_listen_address: 0.0.0.0
    axon_agent_redhat_repository: "https://packages.axonops.com/yum"
    es_redhat_repository_url: https://artifacts.elastic.co/packages/7.x/yum

  roles:
    - role: cassandra
      tags: cassandra
      when: install_cassandra is defined and install_cassandra
    - role: elastic
      tags: elastic
      when: install_elastic is defined and install_elastic
    - role: server
      tags: server, axonops-server
    - role: dash
      tags: dash, axonops-dashboard
```

***

*This project may contain trademarks or logos for projects, products, or services. Any use of third-party trademarks or logos are subject to those third-party's policies. AxonOps is a registered trademark of AxonOps Limited. Apache, Apache Cassandra, Cassandra, Apache Spark, Spark, Apache TinkerPop, TinkerPop, Apache Kafka and Kafka are either registered trademarks or trademarks of the Apache Software Foundation or its subsidiaries in Canada, the United States and/or other countries. Elasticsearch is a trademark of Elasticsearch B.V., registered in the U.S. and in other countries. Docker is a trademark or registered trademark of Docker, Inc. in the United States and/or other countries.*
