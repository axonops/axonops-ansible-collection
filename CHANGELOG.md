# Changelog

All notable changes to this collection are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **CLI `health` command**: reports the health of every cluster visible to the
  organisation. A new `Orgs` component queries `/api/v1/orgs` and flattens the
  returned org / type / cluster tree, mapping status `0`/`1`/`2` to
  `OK`/`Warning`/`Error` (anything else is `Unknown`). By default only the
  clusters that are not OK are printed; `--show-healthy` also lists the healthy
  clusters and the nodes of `--cluster`, and `--show-orgs` lists the visible
  organisations. The command exits `1` when any cluster is not OK, so it can be
  used as a check in a script or a CI job.

### Changed

- **CLI**: the `info` command is now `health`. The connection and authentication
  summary it used to print is shown only with `-v`; the default output is the
  cluster health report.

- **CLI**: all API endpoints are now declared in a single `axonopscli/urls.py`
  module instead of a per-component class attribute, so changing an endpoint is
  a one-line edit in one place.

### Fixed

- **CLI**: the nodes endpoint in `AxonOps.find_nodes_ids` was missing its
  leading slash, so it was concatenated onto the host with no separator.

- **configurations role**: opt-in health / config check via the `info` tag
  (tagged `info` + `never`, so it only runs with `--tags info`). It queries the
  AxonOps API for the target `org` and `cluster`, validates the `use_saml`
  setting by retrying once with the opposite value (failing with a clear message
  if the opposite value is the one that works), and fails the play if any
  monitored component reports a non-zero `status`, returning a structured
  `unhealthy` list.
- **info module**: `use_saml` documentation, SAML flip-retry health check, and
  component status validation (`unhealthy` return field).
- **chrony role**: installs and configures chrony (`chronyd`) for NTP time
  synchronization, critical for Cassandra (timestamp-based conflict
  resolution, LWTs), Kafka, and OpenSearch/Elasticsearch cluster health.
  Standalone role with no dependencies. NTP-related variable names
  (`ntp_prefered_server`, `ntp_secondary_server`, `ntp_third_server`,
  `ntp_fourth_server`, `ntp_servers`, `ntp_pool_hosts`,
  `ntp_allowed_clients`, `chrony_extra_options`) intentionally match the
  legacy Digitalis `ar-chrony` role for drop-in compatibility. Also stops,
  disables, and masks `systemd-timesyncd` when present by default
  (`chrony_disable_timesyncd: true`) to avoid two NTP clients fighting.
  ([#119](https://github.com/axonops/axonops-ansible-collection/issues/119))

### Changed

- **configurations role**: the preamble tasks (`org`/`cluster`/`cluster_type`
  resolution and the required-variable assertion) are now tagged `always`, so
  `--tags info` (and other tag selections) run the required setup standalone.
- **cassandra (BREAKING)**: `cassandra_data_directory` now defaults to
  `/var/lib/cassandra/data` (previously `/var/lib/cassandra`), matching the
  upstream Apache Cassandra layout. New installs are unaffected. Existing
  clusters that relied on the old default must either migrate keyspace data
  into the new path (see "Upgrade Notes" in `roles/cassandra/README.md`) or
  pin `cassandra_data_directory: /var/lib/cassandra`.
  ([#96](https://github.com/axonops/axonops-ansible-collection/pull/96))

### Fixed

- **alert_route module**: typo `type: srt` corrected to `type: str` in DOCUMENTATION block, fixing Galaxy importer parse failure.
- **cassandra role**: added a `[cassandra311]` yum repo stanza so `cassandra_install_format: pkg` works with `cassandra_version` 3.11.x on RedHat-family hosts (previously only 4.1.x/5.0.x had a repo, causing `No package cassandra-3.11.17-1 available.`). Override via `cassandra_redhat_repository_url_311x`. See `roles/cassandra/README.md` for details. ([#124](https://github.com/axonops/axonops-ansible-collection/issues/124))
- **cassandra role**: added the missing `gpgkey=` directive to all three RedHat yum repo stanzas (`cassandra311`, `cassandra41`, `cassandra50`). Without it, `repo_gpgcheck=1` failed signature verification on the repo metadata even though the GPG key was already imported into the RPM keyring, causing dnf to silently drop the repo and report the package as unavailable instead of surfacing the real GPG error. This was a pre-existing bug affecting all RedHat pkg installs (4.1.x/5.0.x too), not just 3.11.x. ([#124](https://github.com/axonops/axonops-ansible-collection/issues/124))
- **cassandra role**: fixed `ansible.builtin.rpm_key` crashing with `'utf-8' codec can't decode byte 0xe9 ... invalid continuation byte` when importing the Apache Cassandra GPG keys on RedHat-family hosts (ansible-core >= 2.18). Apache's `KEYS` file has one contributor's comment in Latin-1 instead of UTF-8, and `rpm_key` strict-decodes the whole file as text regardless of whether it's given a URL or a local path. The role now imports via `rpm --import` directly, which handles the raw bytes without decoding. ([#124](https://github.com/axonops/axonops-ansible-collection/issues/124))
- **cassandra role**: fixed `rpm --import` failing with `key 1 not an armored public key` on newer rpm (4.19+, e.g. Rocky/RHEL 10), and dnf's own `gpgkey=` handling failing with `Parsing armored OpenPGP packet(s) failed` for the same reason — Apache's `KEYS` file mixes ASCII-armored key blocks with plain-text fingerprint listings, which older rpm tolerated but newer rpm rejects outright. The role now extracts only the `BEGIN/END PGP PUBLIC KEY BLOCK` sections into a persistent local file (`/etc/pki/rpm-gpg/RPM-GPG-KEY-apache-cassandra`), which all three repo stanzas' `gpgkey=` now point at instead of the remote URL; that file's presence also serves as the idempotency marker for the import block. ([#124](https://github.com/axonops/axonops-ansible-collection/issues/124))

### Added

- **cassandra role**: cqlsh now works on hosts whose system Python is >= 3.12
  (Ubuntu 24.04, Debian 13), where the bundled cqlsh aborts on removed stdlib
  modules. The role provisions an isolated Python virtual environment with the
  maintained standalone `cqlsh` package and installs a wrapper at
  `/usr/local/bin/cqlsh` that launches it, shadowing the broken distribution
  `cqlsh` on `PATH` so the plain command works (configurable via
  `cassandra_cqlsh_wrapper_path`). New variables:
  `cassandra_cqlsh_venv_enabled`, `cassandra_cqlsh_venv_path`,
  `cassandra_cqlsh_python`, `cassandra_cqlsh_venv_packages`,
  `cassandra_cqlsh_wrapper_path` (see the cassandra role README for defaults).
  ([#116](https://github.com/axonops/axonops-ansible-collection/issues/116))

- **kafka role**: added `README.md` with full variable reference, quick start, and usage examples; fixes Galaxy publish failure caused by missing role readme.

- **cassandra**: preflight data-directory migration guard. The role now fails
  fast when `cassandra_data_directory` contains no `system` keyspace directory
  while its parent does — the signature of data still laid out with the
  pre-0.6.0 default — instead of rewriting `cassandra.yaml` and restarting
  Cassandra against an empty directory (which would bring the node up empty
  with a new host ID). Controlled by `cassandra_data_directory_check`
  (default `true`).
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

- **cassandra**: the role no longer auto-starts the node on first install
  when `cassandra_start_on_install: false`. The `Start cassandra` task's
  `state` expression had an `{% else %}started` fall-through, so on a fresh
  host — where `cassandra.service` is absent from `ansible_facts.services`
  or `inactive` — it started the node regardless of the flag. The service
  is now left untouched (`omit`) unless start is explicitly requested or the
  node is already running.
  ([#111](https://github.com/axonops/axonops-ansible-collection/issues/111))

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
