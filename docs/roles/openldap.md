# OpenLDAP Role

## Overview

The `openldap` role installs a local OpenLDAP (`slapd`) directory and seeds it with users and groups. AxonOps Server can then use it for LDAP authentication and role mapping. Use it to demo, test or run AxonOps LDAP/RBAC without a corporate directory.

The role:

- installs OpenLDAP from the distribution repositories (EPEL on the RHEL family)
- configures `slapd` through `cn=config` (OLC); it does not use `slapd.conf`
- creates the base DN, a users OU, a groups OU, `groupOfNames` groups and `inetOrgPerson` users
- loads the `memberof` and `refint` overlays so each user carries a `memberOf` attribute
- optionally enables TLS (LDAPS on 636 and StartTLS on 389), with a self-signed or your own certificate
- publishes the `openldap_axon_server_ldap_setting` fact, ready to use as `axon_server_ldap_setting` in the [server](server.md) role

The `server` role does not depend on this role. You can point axon-server at any LDAP directory.

## Requirements

- Ansible 2.15 or higher
- `community.general` collection (LDAP modules): `ansible-galaxy collection install community.general`
- A clean target host with systemd. The role refuses to run on a host that already has an OpenLDAP database it did not create.
- Supported platforms: Rocky Linux / RHEL 9 and 10, Ubuntu 22.04 / 24.04 / 26.04, Debian 12 / 13

The role installs these packages on the target host:

| OS family | Packages | Source |
|-----------|----------|--------|
| RHEL 9 / 10 | `openldap-servers`, `openldap-clients`, `python3-ldap` | EPEL (`openldap-servers`), BaseOS/AppStream (the rest). `epel-release` is installed unless `openldap_install_epel: false`. |
| Debian / Ubuntu | `slapd`, `ldap-utils`, `python3-ldap` | Distribution repositories. `slapd` is preseeded with `slapd/no_configuration`, so the package does not create its own database. |

`python3-ldap` is the `python-ldap` library that the `community.general` LDAP modules need on the managed host. The role installs the packaged build, so no compiler is needed.

## Quick start

```yaml
- name: Local LDAP directory
  hosts: ldap
  become: true
  vars:
    openldap_admin_password: "{{ vault_openldap_admin_password }}"
    openldap_users:
      - uid: alice
        password: "{{ vault_alice_password }}"
        groups: [axonops_admin]
  roles:
    - axonops.axonops.openldap
```

```sh
ansible-playbook -i inventory ldap.yml --ask-vault-pass

# Check the user can bind and has the expected groups
ldapsearch -x -H ldap://ldap-host -D "uid=alice,ou=People,dc=axonops,dc=local" -W \
  -b "uid=alice,ou=People,dc=axonops,dc=local" -s base memberOf
```

## Variables

### Directory

| Variable | Type | Default | Example | Description |
|----------|------|---------|---------|-------------|
| `openldap_admin_password` | string | *(none — required)* | `"{{ vault_openldap_admin_password }}"` | Password for the admin (root) DN. The role fails early if unset. |
| `openldap_base_dn` | string | `dc=axonops,dc=local` | `dc=example,dc=com` | Directory suffix. Must start with `dc=`. Fixed after the first run. |
| `openldap_organization` | string | `AxonOps` | `Example Ltd` | `o` attribute of the base entry. |
| `openldap_admin_dn` | string | `cn=admin,{{ openldap_base_dn }}` | `cn=manager,dc=example,dc=com` | Root DN of the database. |
| `openldap_users_ou` | string | `ou=People` | `ou=Users` | OU for users, relative to the base DN. |
| `openldap_groups_ou` | string | `ou=Groups` | `ou=Roles` | OU for groups, relative to the base DN. |
| `openldap_groups` | list | four AxonOps groups (below) | see below | Groups to create. |
| `openldap_users` | list | `[]` | see below | Users to create. |
| `openldap_enable_memberof` | bool | `true` | `false` | Load the `memberof` and `refint` overlays. Required for `rolesAttribute: memberOf`. |

Default `openldap_groups`:

| `name` | `axon_role` |
|--------|-------------|
| `axonops_super` | `superUserRole` |
| `axonops_admin` | `adminRole` |
| `axonops_readonly` | `readOnlyRole` |
| `axonops_backup` | `backupAdminRole` |

Each group entry takes `name` (required), `description` (optional) and `axon_role` (optional). `axon_role` is the axon-server `rolesMapping` key that the group maps to. A group with no members holds the admin DN as a placeholder member, because `groupOfNames` needs at least one member.

Each `openldap_users` entry takes:

| Key | Required | Example | Description |
|-----|----------|---------|-------------|
| `uid` | yes | `alice` | Login name. The DN is `uid=<uid>,<users_ou>,<base_dn>`. |
| `password` | yes | `"{{ vault_alice_password }}"` | Plaintext password. Stored as a salted SHA-1 (`{SSHA}`) hash. |
| `cn` | no | `Alice Smith` | Common name. Defaults to `uid`. |
| `sn` | no | `Smith` | Surname. Defaults to `uid`. |
| `mail` | no | `alice@example.com` | Email address. |
| `groups` | no | `[axonops_admin]` | Names from `openldap_groups`. |

The role manages group membership, `cn`, `sn`, `mail` and `description` exactly. A user removed from a group's list is removed from that group on the next run. The role does not delete users that you remove from `openldap_users`.

### Listeners and TLS

| Variable | Type | Default | Example | Description |
|----------|------|---------|---------|-------------|
| `openldap_listen_ldap` | bool | `true` | `false` | Listen for LDAP (and StartTLS when TLS is on). |
| `openldap_ldap_port` | int | `389` | `3389` | LDAP port. |
| `openldap_listen_ldaps` | bool | `false` | `true` | Listen for LDAPS. Needs `openldap_tls_mode` other than `disabled`. |
| `openldap_ldaps_port` | int | `636` | `6636` | LDAPS port. |
| `openldap_tls_mode` | string | `disabled` | `generate` | `disabled`, `generate` (self-signed) or `custom`. |
| `openldap_tls_cert` | string | `""` | `files/ldap.crt` | Control-node path to the certificate (PEM). `custom` only. |
| `openldap_tls_key` | string | `""` | `files/ldap.key` | Control-node path to the private key (PEM). `custom` only. |
| `openldap_tls_ca` | string | `""` | `files/ca.crt` | Control-node path to the CA bundle (PEM). Optional. |
| `openldap_tls_common_name` | string | host FQDN | `ldap.example.com` | Certificate CN for `generate`. |
| `openldap_tls_extra_sans` | list | `[]` | `["IP:10.0.0.5"]` | Extra subjectAltNames for `generate`. The CN, `inventory_hostname`, `localhost` and `127.0.0.1` are always added. |
| `openldap_tls_generate_days` | int | `825` | `365` | Validity of the generated certificate. |
| `openldap_tls_protocol_min` | string | `"3.3"` | `"3.4"` | Minimum TLS version: `3.3` = TLS 1.2, `3.4` = TLS 1.3. |

The `ldapi:///` socket is always enabled. The role uses it (as root, SASL EXTERNAL) to change `cn=config`.

### Service and storage

| Variable | Type | Default | Example | Description |
|----------|------|---------|---------|-------------|
| `openldap_install_epel` | bool | `true` | `false` | Install `epel-release` on the RHEL family. Set `false` if you mirror EPEL yourself. |
| `openldap_start_on_install` | bool | `true` | `false` | Start `slapd`. Configuration and seeding need a running `slapd`, so they are skipped when `false`. |
| `openldap_start_on_boot` | bool | `true` | `false` | Enable `slapd` at boot. |
| `openldap_data_dir` | string | `/var/lib/ldap` | `/data/ldap` | MDB database directory. |
| `openldap_db_max_size` | int | `1073741824` | `4294967296` | MDB map size in bytes. |
| `openldap_log_level` | string | `stats` | `none` | `olcLogLevel`. |

### axon-server integration

| Variable | Type | Default | Example | Description |
|----------|------|---------|---------|-------------|
| `openldap_axon_server_host` | string | `openldap_tls_common_name` | `ldap.example.com` | Host name axon-server uses to reach the directory. |
| `openldap_axon_server_insecure_skip_verify` | bool | `true` for `generate`, else `false` | `false` | `insecureSkipVerify` in the published setting. |

The role sets the fact `openldap_axon_server_ldap_setting` on the LDAP host:

```yaml
host: ldap1.example.com
port: 636                 # 389 unless openldap_listen_ldaps is true
useSSL: true              # openldap_listen_ldaps
startTLS: false           # true when TLS is on and LDAPS is off
insecureSkipVerify: true  # openldap_axon_server_insecure_skip_verify
base: dc=axonops,dc=local
bindDN: cn=admin,dc=axonops,dc=local
userFilter: (uid=%s)
rolesAttribute: memberOf
callAttempts: 3
rolesMapping:
  _global_:
    superUserRole: cn=axonops_super,ou=Groups,dc=axonops,dc=local
    adminRole: cn=axonops_admin,ou=Groups,dc=axonops,dc=local
    readOnlyRole: cn=axonops_readonly,ou=Groups,dc=axonops,dc=local
    backupAdminRole: cn=axonops_backup,ou=Groups,dc=axonops,dc=local
```

Keys are camelCase because axon-server reads them verbatim. The fact has no `bindPassword`, so the admin password never reaches a fact cache. Add it with `combine` from your vault, as in the examples.

## Examples

### 1. Standalone directory

```yaml
- name: Standalone LDAP directory
  hosts: ldap
  become: true
  vars:
    openldap_base_dn: "dc=example,dc=com"
    openldap_organization: "Example Ltd"
    openldap_admin_password: "{{ vault_openldap_admin_password }}"
    openldap_users:
      - uid: alice
        cn: Alice Smith
        sn: Smith
        mail: alice@example.com
        password: "{{ vault_alice_password }}"
        groups: [axonops_super]
      - uid: bob
        cn: Bob Jones
        sn: Jones
        password: "{{ vault_bob_password }}"
        groups: [axonops_readonly, axonops_backup]
  roles:
    - axonops.axonops.openldap
```

### 2. Directory with TLS

Self-signed certificate, LDAPS on 636 and StartTLS on 389:

```yaml
- name: LDAP directory with TLS
  hosts: ldap
  become: true
  vars:
    openldap_admin_password: "{{ vault_openldap_admin_password }}"
    openldap_tls_mode: generate
    openldap_tls_common_name: ldap.example.com
    openldap_tls_extra_sans: ["IP:10.0.0.5"]
    openldap_listen_ldaps: true
  roles:
    - axonops.axonops.openldap
```

With your own certificate:

```yaml
    openldap_tls_mode: custom
    openldap_tls_cert: files/ldap.example.com.crt
    openldap_tls_key: files/ldap.example.com.key   # encrypt with ansible-vault
    openldap_tls_ca: files/ca.crt
    openldap_listen_ldaps: true
```

Test the listener. The CA file is `/etc/openldap/tls/ca.crt` on the RHEL family and `/etc/ldap/tls/ca.crt` on Debian and Ubuntu:

```sh
LDAPTLS_CACERT=/etc/ldap/tls/ca.crt ldapwhoami -x -H ldaps://ldap.example.com \
  -D "uid=alice,ou=People,dc=axonops,dc=local" -W
```

### 3. Directory plus AxonOps Server with LDAP authentication

See [`examples/openldap-axon-server.yml`](../../examples/openldap-axon-server.yml). The second play passes the published fact to the `server` role:

```yaml
- name: Deploy AxonOps Server with LDAP authentication
  hosts: axon-server
  become: true
  vars:
    axon_server_org_name: "mycompany"
    axon_server_license_key: "{{ vault_axon_server_license_key }}"
    axon_server_ldap_enabled: true
    axon_server_ldap_setting: >-
      {{ hostvars[groups['ldap'][0]]['openldap_axon_server_ldap_setting']
         | combine({'bindPassword': vault_openldap_admin_password}) }}
  roles:
    - axonops.axonops.server
```

To write the setting by hand instead, copy the values from the fact above into `axon_server_ldap_setting`.

**License requirement:** axon-server only enables LDAP with a valid license key (`axon_server_license_key`). Without one, the `server` role prints a warning and LDAP login does not work.

#### Manual end-to-end check

Run these steps once against a real axon-server:

1. Run `examples/openldap-axon-server.yml` with a valid license key.
2. On the LDAP host, confirm the user's groups:
   `ldapsearch -x -H ldap://localhost -D "uid=alice,ou=People,dc=axonops,dc=local" -W -b "uid=alice,ou=People,dc=axonops,dc=local" -s base memberOf`
3. On the axon-server host, confirm `/etc/axonops/axon-server.yml` has `auth.enabled: true`, `type: LDAP` and the expected `rolesMapping`.
4. Log in to axon-dash as `alice`. The user must get the AxonOps role mapped to `axonops_super` (super user).
5. Log in as `bob`. The user must get read-only access.
6. Log in with a wrong password. The login must fail.

## Security

- **Cleartext by default.** With `openldap_tls_mode: disabled`, bind passwords cross the network unencrypted. The role prints a warning. Use `generate` or `custom` TLS, and LDAPS or StartTLS, for anything beyond local testing.
- **Anonymous access.** Anonymous clients can read only the root DSE and the schema. Only authenticated binds can read directory entries. `userPassword` is readable by nobody except the entry itself (write) and is only used for authentication.
- **Passwords.** `openldap_admin_password` and user passwords have no defaults. Store them with ansible-vault or a secrets manager. The role hashes them with `slappasswd` (`{SSHA}`) before it stores them, and hides them from task output (`no_log`).
- **Bind account for axon-server.** The published setting uses the admin DN as `bindDN`. For a shared environment, create a dedicated user and set `bindDN`/`bindPassword` to that user instead. Any seeded user can search the directory.
- **`insecureSkipVerify`.** With a self-signed certificate (`generate`), axon-server cannot verify the certificate, so the published setting sets `insecureSkipVerify: true` and the role prints a warning. Install the CA on the axon-server host and set `openldap_axon_server_insecure_skip_verify: false`, or use `custom` with a certificate from a trusted CA.

## How it works

1. **Preflight.** Asserts the admin password, base DN, TLS settings, groups and users are valid.
2. **Install.** Installs the packages. On Debian and Ubuntu, `slapd` is preseeded not to create a database.
3. **Bootstrap.** On the first run only, the role builds a minimal `cn=config` tree with `slapadd -n 0`: modules, the core/cosine/nis/inetorgperson schemas, and the MDB database at `olcDatabase={1}mdb`. On the RHEL family this replaces the package's placeholder configuration. If the host already has a database the role did not create, the role stops.
4. **Service.** Sets the listeners (systemd drop-in on the RHEL family, `/etc/default/slapd` on Debian and Ubuntu) and starts `slapd`.
5. **Online configuration.** Over `ldapi:///`, sets the log level, TLS files, ACLs, overlays and the admin password.
6. **Seeding.** Creates the base entry, OUs, users and groups. A password is re-hashed only when a bind with the configured password fails, so reruns report `changed=0`.
7. **Facts.** Publishes `openldap_axon_server_ldap_setting`.

## Limitations

- One directory host. The role does not configure replication.
- `openldap_base_dn` and `openldap_admin_dn` are fixed after the first run.
- Disabling `openldap_enable_memberof` after the first run does not remove the overlays.
- Switching `openldap_tls_mode` back to `disabled` does not remove the TLS settings from `cn=config`.
- The role does not delete users or groups that you remove from the variables.

## Testing

Molecule scenarios in `roles/openldap/molecule/` run on Rocky Linux 9/10, Ubuntu 22.04/24.04/26.04 and Debian 12/13. The containers boot systemd so `slapd` runs.

| Scenario | What it checks |
|----------|----------------|
| `default` | Install, seeding, `memberOf`, correct and wrong password binds, anonymous access limits, hashed passwords, idempotence |
| `tls` | `generate` mode, LDAPS on 636, StartTLS on 389, certificate SANs, idempotence |
| `no-password` | The role stops at the preflight assert when `openldap_admin_password` is unset |

```sh
cd roles/openldap
MOLECULE_DISTRO=debian12 molecule test -s default
```
