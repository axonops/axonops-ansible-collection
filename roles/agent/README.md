# AxonOps Agent ansible role

## Configuration

There are a few configuration options you'll need to update to match your environment:

```yaml
# Server name or IP where the AxonOps server is running
axon_agent_server_host: localhost
# This is used to identity your Organization
axon_agent_customer_name: Digitalis.IO
# The default is to use the server hostname but you can update it to if you need
axon_agent_host_name: "{{ ansible_hostname }}"
```

The AxonOps agent supports DSE and Apache Cassandra. Select your version below. If you leave it empty the Java agent won't be installed.

```yaml
# Possible Options: axon-cassandra3.11-agent, axon-dse6.0-agent, axon-dse6.7-agent, axon-dse5.1-agent or ""
axon_java_agent: ""
```

If you enabled either TLS or mTLS you'll need to provide the SSL certs path. Please note this role does not copy or create the certs, you'll need to do it yourself.

```yaml
# Possible values: disabled, TLS or mTLS
axon_agent_tls_mode: "disabled"
axon_agent_tls_certfile: /path.crt
axon_agent_tls_keyfile: /path.key
axon_agent_tls_cafile: /path.ca
```

## Running

```yaml
- hosts: all
  gather_facts: true
  vars:
    axon_agent_customer_name: MyCompany
  roles:
    - { role: ar-axon-agent, tags: axonops-agent }
```