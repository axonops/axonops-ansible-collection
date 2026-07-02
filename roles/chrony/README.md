# AxonOps Chrony Ansible Role

Installs and configures [chrony](https://chrony-project.org/) (`chronyd`) for NTP time
synchronization.

Accurate, synchronized clocks are critical for the infrastructure this collection deploys:

- **Cassandra** uses cell write-timestamps for last-write-wins conflict resolution and
  lightweight transactions (LWT/Paxos). Clock skew between nodes can silently cause lost
  writes, resurrected tombstones, and incorrect repair results.
- **Kafka** relies on synchronized clocks for log-segment/retention timing, time-based
  indexes, and transactional/producer fencing.
- **OpenSearch/Elasticsearch** reports clock skew as a cluster health problem and
  mis-timestamps documents.

This role is standalone — it has no dependency on any other role in this collection — and is
recommended alongside `cassandra`, `kafka`, and `opensearch` on any host running those
services.

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
| `chrony_driftfile` | OS-specific (`/var/lib/chrony/drift` on RedHat family, `/var/lib/chrony/chrony.drift` on Debian family) | Path to the drift file. |
| `chrony_rtcsync` | `true` | Enable kernel synchronisation of the real-time clock (`rtcsync` directive). |
| `chrony_makestep` | `"1.0 3"` | Value of the `makestep` directive. |
| `chrony_extra_directives` | `[]` | List of extra directives appended verbatim at the end of the rendered config, for tuning not covered by the variables above. |

### Package / service

| Variable | Default | Description |
|----------|---------|--------------|
| `chrony_package_name` | `chrony` | Package name to install. |
| `chrony_service_name` | OS-specific (`chronyd` on RedHat family, `chrony` on Debian family) | systemd unit name. |
| `chrony_config_path` | OS-specific (`/etc/chrony.conf` on RedHat family, `/etc/chrony/chrony.conf` on Debian family) | Destination path for the rendered config. |
| `chrony_service_enabled` | `true` | Whether the service is enabled at boot. |
| `chrony_disable_timesyncd` | `true` | Stop, disable, and mask `systemd-timesyncd` when present, so it does not fight `chronyd` for the NTP client role. Safe to run on hosts where the unit does not exist. |

The service is started (and restarted on config change) automatically once configured; there
is no separate "state" variable to avoid a redundant restart immediately after first install.

## Example Playbook

```yaml
- hosts: cassandra
  become: true
  roles:
    - role: axonops.axonops.chrony
      vars:
        ntp_pool_hosts:
          - 0.pool.ntp.org
          - 1.pool.ntp.org
          - 2.pool.ntp.org
          - 3.pool.ntp.org
```

### Explicit servers with a preferred source

```yaml
- hosts: cassandra
  become: true
  roles:
    - role: axonops.axonops.chrony
      vars:
        ntp_prefered_server: time.cloudflare.com
        ntp_secondary_server: time.google.com
        ntp_allowed_clients:
          - 10.0.0.0/8
```

### Recommended alongside Cassandra, Kafka, and OpenSearch

```yaml
- hosts: cassandra
  become: true
  roles:
    - role: axonops.axonops.chrony
    - role: axonops.axonops.java
    - role: axonops.axonops.cassandra
```

## Dependencies

None.
