# AxonOps Server Ansible Role

Installs and configures the AxonOps server (`axon-server`).

See [docs/roles/server.md](../../docs/roles/server.md) for full variable reference and example playbooks.

## Configuration

```yaml
axon_server_state: present   # present or absent
axon_server_version: latest  # version to install
axon_server_hum: false       # enable human-readable metrics
axon_server_org_name: mycompany  # required
```

## Example Playbook

```yaml
- hosts: axonops_server
  roles:
    - role: axonops.axonops.server
      vars:
        axon_server_org_name: mycompany
        axon_server_version: latest
        axon_server_cql_hosts:
          - localhost:9042
        axon_server_searchdb_hosts:
          - http://127.0.0.1:9200
```

## LDAP Authentication

To enable LDAP, set `axon_server_ldap_enabled: true` and supply `axon_server_ldap_setting`.
**Key names are camelCase** — `bindDN` and `bindPassword`, not `bind_dn` / `bind_password`.

```yaml
axon_server_ldap_enabled: true
axon_server_ldap_setting:
  host: ldap.example.com
  port: 636
  useSSL: true
  startTLS: false
  insecureSkipVerify: false
  # serverName: ldap.example.com  # optional: override TLS SNI hostname (defaults to host)
  base: "dc=example,dc=com"
  bindDN: "cn=svc_account,dc=example,dc=com"
  bindPassword: "{{ vault_ldap_password }}"
  userFilter: "(sAMAccountName=%s)"
  rolesAttribute: memberOf
  callAttempts: 3
  rolesMapping:
    _global_:
      superUserRole: "cn=axonops_superuser,ou=Groups,dc=example,dc=com"
      adminRole: none
      readOnlyRole: "cn=axonops_readonly,ou=Groups,dc=example,dc=com"
      backupAdminRole: none
```

> **Common mistake**: Using `bind_dn` or `bind_password` (snake_case) will produce invalid
> configuration. The AxonOps server requires `bindDN` and `bindPassword` exactly.
