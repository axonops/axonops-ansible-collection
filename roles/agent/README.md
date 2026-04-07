# AxonOps Agent Ansible Role

## Configuration

There are a few configuration options you'll need to update to match your environment:

```yaml
# Server name or IP where the AxonOps server is running
# Leave as the default (agents.axonops.cloud) to connect to the SaaS service
axon_agent_server_host: agents.axonops.cloud
# This is used to identify your Organization
axon_agent_customer_name: MyCompany
# The default is to use the server hostname, override if needed
axon_agent_host_name: "{{ ansible_hostname }}"
```

The AxonOps agent supports DSE and Apache Cassandra. Select your version below. If you leave it empty the Java agent won't be installed.

```yaml
# Possible options: axon-cassandra3.11-agent, axon-cassandra4.0-agent, axon-cassandra4.1-agent,
#                   axon-cassandra5.0-agent-jdk17, axon-dse5.1-agent, axon-dse6.0-agent,
#                   axon-dse6.7-agent, or ""
axon_java_agent: "axon-cassandra5.0-agent-jdk17"
```

If you enabled either TLS or mTLS you'll need to provide the SSL certs path. Please note this role does not copy or create the certs, you'll need to do it yourself.

```yaml
# Possible values: disabled, TLS or mTLS
axon_agent_tls_mode: "disabled"
axon_agent_tls_certfile: /path/to/cert.crt
axon_agent_tls_keyfile: /path/to/cert.key
axon_agent_tls_cafile: /path/to/ca.crt
```

## Running

```yaml
- hosts: cassandra
  gather_facts: true
  vars:
    axon_agent_customer_name: MyCompany
  roles:
    - role: axonops.axonops.agent
      tags: axonops-agent
```
