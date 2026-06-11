# Changelog

All notable changes to this collection are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **cassandra**: Apache Cassandra 3.11 support. The role now installs and
  configures Cassandra 3.11.x via tar, using a dedicated `templates/3.11.x/`
  set (legacy `cassandra.yaml` schema with `*_in_ms` / `*_in_mb` keys, single
  `jvm.options` file, no `auto_optimise_*` / `commitlog_sync_group_window`
  keys). The `java` role automatically picks Java 8 when `cassandra_version`
  starts with `3.11`. New molecule scenario `cassandra-3.11` and example
  playbook `examples/cassandra-3.11.yml`.
  ([#108](https://github.com/axonops/axonops-ansible-collection/issues/108))
- **preflight**: Amazon Linux added to the supported-OS allowlist
  (`Ubuntu, Debian, CentOS, RedHat, Rocky, Amazon`). All other roles
  already branch on `ansible_os_family`, which Amazon Linux reports
  as `RedHat`, so no further changes were required.
- **cassandra**: jemalloc install on Amazon Linux. The
  `epel-release` package is not available in the Amazon Linux
  repositories (`No package epel-release available.`); skip that
  task on Amazon Linux and install `jemalloc` directly from the
  distribution's own repos (where it is shipped by default on
  Amazon Linux 2023 and via `amazon-linux-extras` on AL2).

### Fixed

- **cassandra**: `cassandra_jemalloc_enabled` default used Jinja
  statement syntax (`{% true if ... %}`) instead of an expression,
  causing `Encountered unknown tag 'true'` whenever the variable was
  evaluated (e.g. by the jemalloc install task's `when:`). Now an
  expression: `{{ ansible_facts['os_family'] == 'Debian' }}`.

- **cassandra 3.11 cassandra.yaml**: unit-aware conversion of friendly
  defaults to legacy `_in_ms` / `_in_kb` / `_in_mb` /
  `_megabits_per_sec` keys. The shared role defaults carry units
  (`"2s"`, `"30m"`, `"10MiB"`, `"24MiB/s"`); the previous 3.11 vars
  file stripped non-digits with `regex_replace`, so `"2s"` rendered as
  `write_request_timeout_in_ms: 2` (= 2 ms), `"30m"` as
  `roles_validity_in_ms: 30`, etc. This silently broke timeouts and
  triggered `Back-pressure window size must be >= 10` at boot because
  the back-pressure window derives from `write_request_timeout_in_ms`.
  The 3.11 vars file now multiplies each value by the unit's base
  count (`s=1000`, `m=60000`, `MiB=1`, `MiB/s -> *8` for the
  megabits-per-sec stream throughput vars) so user overrides in
  either form land on the correct integer 3.11 expects.

- **cassandra 3.11 cassandra.yaml**: stop seeding
  `cassandra_native_transport_port_ssl` with `9142` in the 3.11 vars
  file. Cassandra 3.11 refuses to start when the key is set unless
  `client_encryption_options.enabled: true` (`Encryption must be
  enabled in client_encryption_options for native_transport_port_ssl`).
  The variable is now undefined by default and must be opted into
  alongside client encryption.

- **cassandra 3.11 cassandra.yaml**: socket buffer + index summary keys no
  longer emit empty values that crash Cassandra at boot
  (`Can not set int field … to null value` /
  `internode_send_buff_size_in_bytes:`). The 3.11 vars file used to seed
  `cassandra_{rpc,internode}_{send,recv}_buff_size_in_bytes` and
  `cassandra_index_summary_capacity_in_mb` with `""`; the template's
  `is defined` guard then evaluated true and rendered the key with no
  value. The vars are now left undefined and the template guards also
  reject empty strings, so Cassandra falls back to its JVM defaults
  (or `net.ipv4.tcp_{r,w}mem` for the socket buffers). Also fixed two
  mismatched-variable bugs carried over from the reference template:
  `internode_recv_buff_size_in_bytes` was guarded by
  `cassandra_rpc_recv_buff_size_in_bytes`, and `broadcast_address` was
  guarded by `cassandra_memtable_broadcast_address`.

- **cassandra 3.11 cassandra.yaml**: `key_cache_save_period`,
  `row_cache_save_period`, and `counter_cache_save_period` are now
  rendered as integer seconds. The shared role defaults are duration
  strings (`"4h"` / `"0s"` / `"2h"`) accepted by 4.1.x / 5.0.x but
  rejected by 3.11 (`Cannot create property=key_cache_save_period …
  For input string: "4h"`). The 3.11 vars file converts the friendly
  defaults — and any user override in the same form — to seconds
  before the template renders them.

- **cassandra 3.11 jvm.options**: render `-XX:ParallelGCThreads` and
  `-XX:ConcGCThreads` only when set to a value `> 0`. Java 8's G1GC rejects
  `0` for these (`The flag -XX:+UseG1GC can not be combined with
  -XX:ParallelGCThreads=0`) and refuses to start. When unset (or `0`), the
  lines are emitted as comments so the JVM auto-picks based on core count.

- **cassandra**: `cassandra_use_password_files` no longer breaks Cassandra
  startup. The `keystore_password_file:` / `truststore_password_file:` keys it
  emitted were introduced in Apache Cassandra 6.0 (CASSANDRA-13428) and are
  not recognised by 3.11.x, 4.1.x, or 5.0.x — Cassandra rejected them with
  `Invalid yaml. Please remove properties [...]` and refused to boot. The
  feature now defaults to `false` and is force-disabled with a warning if
  enabled, falling back to inline `keystore_password:` / `truststore_password:`.
  ([#102](https://github.com/axonops/axonops-ansible-collection/issues/102))

- **cassandra**: `cassandra.yaml` template and the new password-file task have
  always read `cassandra_ssl_keystore_pass`, but the defaults file only
  declared `cassandra_ssl_internode_keystore_pass` — so the documented default
  had no effect on the rendered config. Both names are now declared:
  `cassandra_ssl_internode_keystore_pass` (legacy) holds the value;
  `cassandra_ssl_keystore_pass` defaults to it via Jinja indirection. Existing
  playbooks setting either variable continue to work without changes.
  ([#99](https://github.com/axonops/axonops-ansible-collection/issues/99))
- **cassandra 4.1.x template**: `server_encryption_options` now emits a
  `keystore_password:` (or `keystore_password_file:`) entry. The previous
  4.1.x template left the key commented out, so JKS internode TLS could not
  load the keystore. ([#99](https://github.com/axonops/axonops-ansible-collection/issues/99))
