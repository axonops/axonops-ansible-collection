# Chrony Role

## Overview

The `chrony` role installs and configures [chrony](https://chrony-project.org/) (`chronyd`)
for NTP time synchronization. Accurate, synchronized clocks are critical for the
infrastructure this collection deploys:

- **Cassandra** uses cell write-timestamps for last-write-wins conflict resolution and
  lightweight transactions (LWT/Paxos). Clock skew between nodes can silently cause lost
  writes, resurrected tombstones, and incorrect repair results.
- **Kafka** relies on synchronized clocks for log-segment/retention timing, time-based
  indexes, and transactional/producer fencing.
- **OpenSearch/Elasticsearch** reports clock skew as a cluster health problem and
  mis-timestamps documents.

This role is standalone and has no dependency on any other role in this collection. It is
recommended alongside `cassandra`, `kafka`, and `opensearch` on any host running those
services.

## Requirements

- Ansible 2.10 or higher
- Target system running a supported Linux distribution (EL, Fedora, Debian, Ubuntu)

## Compatibility with the legacy `ar-chrony` role

The NTP-related variable names (`ntp_prefered_server`, `ntp_secondary_server`,
`ntp_third_server`, `ntp_fourth_server`, `ntp_servers`, `ntp_pool_hosts`,
`ntp_allowed_clients`, `chrony_extra_options`) intentionally match the legacy Digitalis
`ar-chrony` role, so existing playbooks/inventories can switch from `ar-chrony` to
`axonops.axonops.chrony` without renaming any variables.

## Role Variables

### NTP servers

| Variable | Default | Description |
|----------|---------|--------------|
| `ntp_prefered_server` | `pool.ntp.org` | Preferred NTP server. Rendered with the `prefer` directive. |
| `ntp_secondary_server` | *(unset)* | Additional individually named server. |
| `ntp_third_server` | *(unset)* | Additional individually named server. |
| `ntp_fourth_server` | *(unset)* | Additional individually named server. |
| `ntp_servers` | `[]` | List of additional NTP servers, each rendered as `server <host> iburst`. |
| `ntp_pool_hosts` | `[]` | List of NTP pool hostnames, each rendered as `pool <host> iburst`. |
| `ntp_allowed_clients` | `[]` | List of subnets/hosts allowed to query this host as an NTP server/peer, rendered as `allow <entry>`. |
| `chrony_extra_options` | `""` | Extra options appended to the preferred server line, e.g. `"minpoll 4 maxpoll 6"`. |

### chrony.conf tuning

| Variable | Default | Description |
|----------|---------|--------------|
| `chrony_driftfile` | OS-specific | Path to the drift file (`/var/lib/chrony/drift` on RedHat family, `/var/lib/chrony/chrony.drift` on Debian family). |
| `chrony_rtcsync` | `true` | Enable kernel synchronisation of the real-time clock (`rtcsync` directive). |
| `chrony_makestep` | `"1.0 3"` | Value of the `makestep` directive. |
| `chrony_extra_directives` | `[]` | List of extra directives appended verbatim at the end of the rendered config, for tuning not covered by the variables above. |

### Package / service

| Variable | Default | Description |
|----------|---------|--------------|
| `chrony_package_name` | `chrony` | Package name to install. |
| `chrony_service_name` | OS-specific | systemd unit name (`chronyd` on RedHat family, `chrony` on Debian family). |
| `chrony_config_path` | OS-specific | Destination path for the rendered config (`/etc/chrony.conf` on RedHat family, `/etc/chrony/chrony.conf` on Debian family). |
| `chrony_service_enabled` | `true` | Whether the service is enabled at boot. |
| `chrony_start_on_install` | `true` | Whether chronyd is actually started/restarted by this role run. Independent of `chrony_service_enabled` (boot-time enablement always applies). Set to `false` in environments that don't grant `CAP_SYS_TIME` (chronyd needs it to adjust the system clock via `adjtimex()`) — for example this role's own Docker-based molecule tests. |
| `chrony_disable_timesyncd` | `true` | Stop, disable, and mask `systemd-timesyncd` when present, so it does not fight `chronyd` for the NTP client role. Safe to run on hosts where the unit does not exist. |

## Dependencies

None.

## Example Playbooks

### Basic (public NTP pool)

```yaml
- name: Synchronize time with public NTP pool
  hosts: cassandra
  become: true
  vars:
    ntp_pool_hosts:
      - 0.pool.ntp.org
      - 1.pool.ntp.org
      - 2.pool.ntp.org
      - 3.pool.ntp.org
  roles:
    - role: axonops.axonops.chrony
```

### Explicit servers with a preferred source and access control

```yaml
- name: Synchronize time with internal NTP servers
  hosts: cassandra
  become: true
  vars:
    ntp_prefered_server: time.cloudflare.com
    ntp_secondary_server: time.google.com
    ntp_allowed_clients:
      - 10.0.0.0/8
  roles:
    - role: axonops.axonops.chrony
```

### Advanced tuning

```yaml
- name: Synchronize time with advanced chrony tuning
  hosts: cassandra
  become: true
  vars:
    ntp_prefered_server: time.cloudflare.com
    chrony_extra_options: "minpoll 4 maxpoll 6"
    chrony_makestep: "1.0 -1"
    chrony_extra_directives:
      - "leapsectz right/UTC"
  roles:
    - role: axonops.axonops.chrony
```

### Complete stack with Cassandra

```yaml
- name: Deploy Cassandra with synchronized time
  hosts: cassandra
  become: true
  vars:
    ntp_pool_hosts:
      - 0.pool.ntp.org
      - 1.pool.ntp.org

  roles:
    - role: axonops.axonops.chrony
      tags: chrony

    - role: axonops.axonops.java
      tags: java

    - role: axonops.axonops.cassandra
      tags: cassandra
```

## Notes

- **systemd-timesyncd conflict**: running both `systemd-timesyncd` and `chronyd` as NTP
  clients on the same host is a common source of sync bugs. By default this role disables
  `systemd-timesyncd` when present (`chrony_disable_timesyncd: true`). Set it to `false` if
  you manage that interaction yourself.
- **Idempotency**: re-running the role with the same variables reports no changes to the
  rendered config or the service state.
- **Containers without `CAP_SYS_TIME`**: chronyd needs `CAP_SYS_TIME` to adjust the system
  clock via `adjtimex()`. Some container runtimes don't grant this even when running
  privileged (this is why `chrony_start_on_install: false` is used in this role's own
  molecule tests). Set `chrony_start_on_install: false` if you need to install and configure
  chrony without actually starting it.

## License

See the main collection LICENSE file.

## Author

AxonOps Limited
