# openldap

Installs a local OpenLDAP (`slapd`) directory, seeds it with users and groups, and publishes a ready-made LDAP setting for AxonOps Server. Use it to run AxonOps LDAP authentication and role mapping without a corporate directory.

Full documentation: [docs/roles/openldap.md](../../docs/roles/openldap.md).

## Quick start

```yaml
- name: Local LDAP directory
  hosts: ldap
  become: true
  vars:
    # vault_* variables come from an ansible-vault encrypted vars file,
    # e.g. group_vars/ldap/vault.yml (run with --ask-vault-pass).
    openldap_admin_password: "{{ vault_openldap_admin_password }}"
    openldap_users:
      - uid: alice
        password: "{{ vault_alice_password }}"
        groups: [axonops_admin]
  roles:
    - axonops.axonops.openldap
```

Then point axon-server at it:

```yaml
axon_server_ldap_enabled: true
axon_server_ldap_setting: >-
  {{ hostvars[groups['ldap'][0]]['openldap_axon_server_ldap_setting']
     | combine({'bindPassword': vault_openldap_admin_password}) }}
```

See [`examples/openldap-axon-server.yml`](../../examples/openldap-axon-server.yml) for a full playbook.

## Requirements

- `community.general` collection
- systemd on the target host
- Rocky Linux / RHEL 9 or 10 (packages from EPEL), Ubuntu 22.04 / 24.04 / 26.04, Debian 12 / 13

## Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `openldap_admin_password` | *(required)* | Admin (root DN) password. No default. |
| `openldap_base_dn` | `dc=axonops,dc=local` | Directory suffix. Must start with `dc=`. |
| `openldap_organization` | `AxonOps` | `o` attribute of the base entry. |
| `openldap_admin_dn` | `cn=admin,{{ openldap_base_dn }}` | Root DN. |
| `openldap_users_ou` | `ou=People` | Users OU. |
| `openldap_groups_ou` | `ou=Groups` | Groups OU. |
| `openldap_groups` | `axonops_super`, `axonops_admin`, `axonops_readonly`, `axonops_backup` | List of `{name, description, axon_role}`. `axon_role` is the axon-server `rolesMapping` key: `superUserRole`, `adminRole`, `readOnlyRole` or `backupAdminRole`. See [full docs](../../docs/roles/openldap.md#directory). |
| `openldap_users` | `[]` | Users: `{uid, password, cn, sn, mail, groups}`. |
| `openldap_enable_memberof` | `true` | Load the `memberof` and `refint` overlays. |
| `openldap_listen_ldap` | `true` | Listen on `openldap_ldap_port` (389). |
| `openldap_listen_ldaps` | `false` | Listen on `openldap_ldaps_port` (636). Needs TLS. |
| `openldap_tls_mode` | `disabled` | `disabled`, `generate` or `custom`. |
| `openldap_tls_cert` | `""` | Control-node path to the PEM certificate (`custom` only). |
| `openldap_tls_key` | `""` | Control-node path to the PEM private key (`custom` only). |
| `openldap_tls_ca` | `""` | Control-node path to the PEM CA bundle (`custom`, optional). |
| `openldap_tls_generate_days` | `825` | Validity of the `generate` certificate, in days. |
| `openldap_tls_common_name` | host FQDN | Certificate CN for `generate`. |
| `openldap_tls_extra_sans` | `[]` | Extra subjectAltNames for `generate`. |
| `openldap_tls_protocol_min` | `"3.3"` | Minimum TLS version (`3.3` = TLS 1.2, `3.4` = TLS 1.3). |
| `openldap_install_epel` | `true` | Install `epel-release` on the RHEL family. |
| `openldap_start_on_install` | `true` | Start `slapd`. Configuration and seeding need it. |
| `openldap_start_on_boot` | `true` | Enable `slapd` at boot. |
| `openldap_data_dir` | `/var/lib/ldap` | MDB database directory. |
| `openldap_db_max_size` | `1073741824` | MDB map size in bytes (1 GiB). |
| `openldap_log_level` | `stats` | `olcLogLevel`. |
| `openldap_axon_server_host` | `openldap_tls_common_name` | Host name in the published axon-server setting. |
| `openldap_axon_server_insecure_skip_verify` | `true` for `generate` | `insecureSkipVerify` in the published setting. |

## Security

With `openldap_tls_mode: disabled`, passwords cross the network in cleartext. Use `generate` or `custom` TLS for anything beyond local testing. Anonymous clients can read only the root DSE and schema.

## Testing

```sh
cd roles/openldap
MOLECULE_DISTRO=rockylinux9 molecule test -s default   # also: tls, no-password
```

## License

Apache-2.0

## Contact

Maintained by [AxonOps](https://axonops.com). Support at [axonops.com/contact](https://axonops.com/contact).
