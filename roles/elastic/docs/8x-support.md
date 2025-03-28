# 8.x support

In [December 2021](https://github.com/elastic/ansible-elasticsearch/pull/838), we made the hard decision to deprecate this Ansible playbook without adding support for Elasticsearch 8.X.
We acknowledge the impact this has had on many developers and organizations, and while we are not reverting the decision, we decided to share some guidelines around how to proceed from here, for folks wanting to keep using this playbook with Elasticsearch 8.X.

---

At a high level, this role is expected to work in most cases for fresh installs and upgrades from 7.17+ by only overriding the `es_version` variable as long as the security is enforced properly using the [SSL/TLS doc](ssl-tls-setup.md).

1. install the last released version of the role from galaxy: `ansible-galaxy install elastic.elasticsearch,v7.17.0`

2. copy the TLS PKCS12 keystore and truststore (https://www.elastic.co/guide/en/elasticsearch/reference/current/security-settings.html#security-http-pkcs12-files)

3. write a minimal playbook to deploy 8.2.3 on localhost:
```yaml
- hosts: localhost
  roles:
    - elastic.elasticsearch
  vars:
    es_version: 8.2.3
    es_api_basic_auth_username: elastic
    es_api_basic_auth_password: changeme
    es_enable_http_ssl: true
    es_enable_transport_ssl: true
    es_ssl_keystore: "certs/keystore-password.p12"
    es_ssl_truststore: "certs/truststore-password.p12"
    es_ssl_keystore_password: password1
    es_ssl_truststore_password: password2
    es_validate_certs: no
```

4. deploy locally: `ansible-playbook es.yml`

## Context for the below experiment

The intent is to assess if the current playbook can still work with ES 8.X and what modifications may be needed. The testing was done on Ubuntu 20.04 and CentOS7 GCP VMs.

The only code change done in the Ansible playbook was the override of the `es_version` variable.

### What is working

- ✅ Deploying a standalone Elasticsearch cluster in 8.2.3 with the security example playbook from 7.x:
- ✅ managing Elasticsearch users
- ✅ upgrading a 7.17.0 standalone cluster **with security already enabled** to 8.2.3
- ✅ managing Elasticsearch license

The below configuration was used in the tests

```yaml
- hosts: localhost
  roles:
  - elastic.elasticsearch
  vars:
    es_config:
      xpack.security.authc.realms.file.file1.order: 0
    es_api_basic_auth_username: elastic
    es_api_basic_auth_password: changeme
    es_api_sleep: 5
    es_enable_http_ssl: true
    es_enable_transport_ssl: true
    es_ssl_keystore: "test/integration/files/certs/keystore-password.p12"
    es_ssl_truststore: "test/integration/files/certs/truststore-password.p12"
    es_ssl_keystore_password: password1
    es_ssl_truststore_password: password2
    es_validate_certs: no
    es_users:
      file:
        es_admin:
          password: changeMe
          roles:
          - admin
        testUser:
          password: changeMeAlso!
          roles:
          - power_user
          - user
    es_roles:
      file:
        admin:
          cluster:
          - all
          indices:
          - names: '*'
             privileges:
              - all
      power_user:
        cluster:
          - monitor
        indices:
          - names: '*'
            privileges:
              - all
      user:
        indices:
          - names: '*'
            privileges:
              - read
```

### What is not working

**Deploying an 8.X cluster with the default Ansible configuration (no security) will not work.**

When runnin Elasticsearch 8.x outside of Ansible without any security configuration, Elasticsearch will autogenerate a security configuration and still activate security.
However, when you run Elasticsearch 8.x as part of the Ansible role without any security configuration, this will fail because the Ansible role will not be able to retrieve and use the autogenerated security configuration.

To tackle this, you always have to specify your own security configuration based on the [SSL/TLS doc](ssl-tls-setup.md).


### What has not been tested

**Deploying a 3 nodes cluster**

When trying to deploy a 3 nodes clusters, the nodes seem to be configured successfully but they aren't able to communicate together with the test certificates (the ones used in automated standalone tests). It's highly likely that the problem lies with the tests certs themselves and not with the role.

Should you be able to deploy a multi-node clusters, you will most likely have to change the configuration to use the new `node.roles` parameter ([example](https://github.com/elastic/ansible-elasticsearch/pull/772)) instead of the `node.master` and `node.data` (which got deprecated in 7.9, but the role never got [fixed](https://github.com/elastic/ansible-elasticsearch/issues/731).
