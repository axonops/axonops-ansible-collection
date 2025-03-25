# AxonOps Ansible Collection

This collection provides Ansible roles and playbooks to deploy AxonOps components. The examples below
show how you can install the AxonOps server with Elasticsearch and Cassandra to store metrics and configurations
and how you can install also the AxonOps agent to Apache Cassandra

## Playbooks

### Inventory

Before you can start using these playbooks you'll need to add your nodes to the inventory. You can find an example
in the [./example](./example) directory. There are two sections:

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

If you have a local mirror repository of the AxonOps packages adjust the `axon_agent_redhat_repository` URL.

```yaml
- name: Deploy AxonOps Agent
  hosts: cassandra
  become: true
  vars:
    axon_java_agent: "axon-cassandra4.1-agent"
    axon_agent_version: "1.0.131"
    axon_java_agent_version: "1.0.14"
    customer_name: example
    java_pkg: java-11-openjdk-headless
    axon_agent_redhat_repository: "https://packages.axonops.com/yum"
    cassandra_redhat_repository_url: https://redhat.cassandra.apache.org/41x/
    # Set to false if you already have Apache Cassandra running
    install_cassandra: true

  roles:
    - role: agent
      tags: agent, axonops-agent
      vars:
        axon_agent_server_host: "{{ groups['axon-server'] | first }}"
        cassandra_dc: "DC1"
        cassandra_seeds: "{{ groups['cassandra'] | map('extract', hostvars, ['ansible_default_ipv4', 'address']) | list | first }}"
    - role: cassandra
      tags: cassandra
      when: install_cassandra
      vars:
        cassandra_dc: "example"

  post_tasks:
    - name: Add axonops to the cassandra group
      tags: user
      ansible.builtin.user:
        name: cassandra
        groups: cassandra,axonops
        append: true
      notify:
        - restart axon-agent
        - Restart Cassandra
```

### axon-server.yml

This playbook deploys the AxonOps Server. It installs a local Apache Cassandra server to use a metrics
storage and it will also deploy Elasticsearch for the AxonOps configuration.

For more information about the Elasticsearch installation options please see the following [README.md](./roles/elastic/README.md)

```yaml
- name: Deploy AxonOps Server
  hosts: axon-server
  become: true
  vars:
    install_cassandra: true
    install_elastic: true
    java_pkg: java-11-openjdk-headless
    axon_server_cql_hosts:
      - localhost:9042
    axon_dash_listen_address: 0.0.0.0
    axon_agent_redhat_repository: "https://packages.axonops.com/yum"

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
