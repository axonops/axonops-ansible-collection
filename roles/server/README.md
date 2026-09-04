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

## Reporting service (Reports v2)

From Reports v2, the `axon_dash` config block and `axon_dash_url` option are removed from the
AxonOps Server config. This role only ever templated the scalar `axon_dash_url` (never an
`axon_dash:` block), and now gates it to `axon_server_version < 2.0.4`. For `latest` or `>= 2.0.4`
it instead templates `axon_reports_url` from `axon_server_reports_url` (env `AXON_REPORTS_URL`),
telling the server where to reach the reporting service.

```yaml
axon_server_reports_url: "http://127.0.0.1:8081"  # default; where axon-server reaches axon-reporting
```

The reporting service (`axon-reporting`) is installed and run by the `dash` role, since it must
be co-located with `axon-dash`. Override `axon_server_reports_url` when `axon-dash` runs on a
different host to `axon-server`. For `axon-server < 2.0.4`, the legacy `axon_dash_url` variable is
still templated when set.

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
