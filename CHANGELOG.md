# Changelog

All notable changes to this collection are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **`examples/self-hosted-example/` was not runnable as documented**: the playbooks and inventories
  referenced group names that do not exist, and the AxonOps Server inventory was missing required
  variables. Every group reference now resolves against the three documented groups
  (`axonops_server`, `axonops_searchdb`, `axonops_cassandra`):
  - `axon-cassandra.yml`, `inventories/cassandra.yml` and `cassandra-5.0.yml` referenced
    `groups['cassandra']` and `groups['axon-server']`, neither of which is defined, so the plays
    failed on an undefined variable.
  - `inventories/axonops.yml` derived `cassandra_seeds` from `groups['axonops_cassandra']`, a group
    that inventory does not define, and carried a block of `cassandra_*` / `axon_agent_*` variables
    under `axonops_searchdb`, where no Cassandra host ever reads them.
  - `axon_server_org_name` was set in neither inventory, so step 3 of both README quick starts
    aborted on the `server` role assert: `axon_server_org_name must be set`.
  - `axon_server_searchdb_*` (including the OpenSearch admin credentials) sat under
    `axonops_searchdb` group vars while the `server` role runs on `axonops_server`; it only worked
    because one host happened to be in both groups. These, plus the new `axon_server_cql_hosts`
    metrics-store settings, now live on `axonops_server`.
  - `inventories/axonops.yml` built `axon_server_searchdb_hosts` from `groups['axonops_server']`,
    pointing AxonOps Server at itself instead of at the Elasticsearch nodes.
  - `es_master_nodes` was a hand-maintained one-element list naming the single `node.master: true`
    node, leaving the Elasticsearch cluster with no quorum and no `cluster.initial_master_nodes`,
    so a fresh cluster never bootstrapped. All three nodes are now master-eligible and hold data,
    and both `discovery.seed_hosts` and `cluster.initial_master_nodes` are derived from the
    `axonops_searchdb` group. The unused `es_master_nodes` variable is gone, along with the
    per-host `es_config` blocks that had drifted (a missing `node.name`, a missing `http.host`).
  - `axon-cassandra.yml` documented itself as deploying the AxonOps Agent but never included the
    `agent` role; it now does, and its host-specific variables moved to `inventories/cassandra.yml`
    so play vars no longer silently override the inventory.
  - The dashboard was left on the `axon_dash_listen_address` default of `127.0.0.1`, unreachable
    from outside the server. Both inventories now bind it explicitly.
  - README quick start step 4 ran `axon-cassandra.yml` against `inventories/axonops-opensearch.yml`,
    which defines no Cassandra group, so the play matched zero hosts and silently did nothing. The
  - The inventory groups were renamed from hyphens to underscores (`axonops-server` →
    `axonops_server`, and likewise for `axonops_searchdb` / `axonops_cassandra`). Ansible warned
    `Invalid characters were found in group names` on every run, because a hyphen is not a valid
    Python identifier and so cannot be used unquoted in Jinja. Role tag names are unchanged.

    README now documents the group contract, the required variables, Cassandra before server
    ordering, and how to reach the dashboard.

- **OpenSearch on aarch64**: the `opensearch` role hardcoded the `linux-x64` tarball, so on an
  arm64 host it installed the x86-64 bundle and the service died 70 ms after start with the
  bundled JDK reporting `Exec format error` — masked in the journal, because
  `install_demo_configuration.sh` discards stderr and `opensearch-tar-install.sh` prints an
  unrelated `OPENSEARCH_INITIAL_ADMIN_PASSWORD` banner unconditionally. The download URL now uses
  the new `opensearch_arch` variable, derived from `ansible_architecture` (`x64` / `arm64`) and
  overridable, and the cached tarball path is arch-qualified so a stale wrong-arch download is not
  reused. A preflight assert rejects other architectures with an actionable message instead of
  installing an unrunnable bundle. Fixes #140. Pre-existing since the role was added in #61; not
  a regression from the version bump above.

### Changed

- **Default Apache Cassandra version bumped to 5.0.9**: `cassandra_version` (already `5.0.9` in
  `roles/cassandra/defaults/main.yml`) is now consistent everywhere — `k8ssandra_cassandra_version`
  and `k8ssandra_image_tag` in `roles/k8ssandra/defaults/main.yml`, all `cassandra` and `k8ssandra`
  molecule scenarios, `examples/k8ssandra.yml`, `examples/full-example/`, and the docs. The
  `ghcr.io/axonops/k8ssandra/cassandra:5.0.9` image tag is published, so no k8ssandra pin is held back.

- **Default OpenSearch version bumped to 3.8.0**: `opensearch_version` in
  `roles/opensearch/defaults/main.yml`, both opensearch molecule scenarios,
  `examples/opensearch.yml`, and the docs. No `opensearch.yml` config keys, security-plugin
  settings, or `searchguard-tlstool` behaviour used by the role changed between 3.6.0 and 3.8.0,
  so the templates are unchanged. `devcluster_opensearch_version` stays on the 2.x line (`2.19.1`)
  by design.

### Added

- **ansible-navigator example**: `examples/ansible-navigator.yml` runs the example playbooks inside
  `ghcr.io/axonops/axonops-ansible-ee`, so a control node needs only a container runtime and
  `ansible-navigator`. `examples/README.md` documents the interactive TUI, `--mode stdout` for CI,
  artifact replay, and the podman and `~/.ssh` mount gotchas.

### Fixed

- **Execution Environment base image**: re-pinned the `centos:stream9` manifest-list digest in
  `ci/execution-environment/execution-environment.yml` to
  `sha256:64e5a212e4f2e7b706dbd822968914bb8def7de0a7fdfd3bf248241f8758101c`. The previous digest
  had been pruned from quay.io, so every EE build failed with
  `failed to resolve source metadata ... not found`.

- **Collection dependencies**: `galaxy.yml` now declares the collections the roles call
  (`ansible.posix`, `community.general`, `community.crypto`, `community.docker`,
  `kubernetes.core`) as `dependencies:`, so `ansible-galaxy collection install axonops.axonops`
  installs them automatically. They are also added to
  `ci/execution-environment/requirements.yml`, fixing execution-environment runs that failed with
  `couldn't resolve module/action 'ansible.posix.sysctl'` because the published
  `ghcr.io/axonops/axonops-ansible-ee` image contained only `axonops.axonops`. The
  self-containment check in `.github/workflows/execution-environment.yml` now asserts every
  collection is present and resolvable with networking disabled, so the regression cannot ship
  again. Fixes [#135](https://github.com/axonops/axonops-ansible-collection/issues/135).

### Changed

- **Release workflow**: tagging the repository now bumps the collection version
  automatically instead of failing when `galaxy.yml` was not updated by hand.
  `.github/workflows/release.yml` derives the version from the `v*` tag, writes it into
  `galaxy.yml` on the default branch and pushes that bump commit, and applies the same
  version to the tree used by the package and publish jobs so the artefact uploaded to the
  GitHub release and to Ansible Galaxy always carries the tagged version. The Execution
  Environment release build follows the same rule: it now bakes in the collection at the tag
  being built instead of failing when `ci/execution-environment/requirements.yml` still pinned
  the previous release, and the release workflow commits the matching pin back to the default
  branch alongside the `galaxy.yml` bump.

### Added

- **Ansible Execution Environment**: new `ci/execution-environment/`
  `ansible-builder` (v3) definition producing `ghcr.io/axonops/axonops-ansible-ee`,
  a self-contained image bundling `ansible-core` 2.18.4, this collection installed from an
  explicit git tag, and the Python dependencies the AxonOps modules need. The base image is
  pinned by manifest digest and nothing is downloaded from Galaxy or PyPI at container start. The
  image carries no entrypoint: consumers pass the playbook to run as the container command, so a
  single image serves every use of the collection from a container.
  `.github/workflows/execution-environment.yml` builds it for `linux/amd64` and `linux/arm64`,
  pushes a version tag plus `latest` on `v*` git tags, and builds without pushing on pull
  requests. `ci/execution-environment/README.md` documents the reproducible local build and
  the published tag scheme.

- **Configurations exporter**: new `configurations_exporter/` tool that exports the
  AxonOps configuration of a cluster as YAML. `configurations_exporter.py` is a thin
  front end over the new `src` package (`application.py`, `axonops.py`, `exporter.py`,
  `urls.py`, `utils.py`). The `export` command reads alert rules, dashboards,
  integrations, health checks, log collectors, silences, adaptive and scheduled
  repairs, backups, commitlog archiving, and agent disconnection tolerance, and writes
  one YAML file per section into `exports/<org>/<cluster>/<section>.yaml`;
  `--section` restricts the export. Sections the API rejects — a cluster with no
  commitlog archiving configured, say — are skipped and named in the summary;
  `--fail-on-error` stops at the first one instead. A `sections` command lists what
  can be exported. Every global option
  (`--org`, `--cluster`, `--cluster-type`, `--token`, `--username`, `--password`,
  `--url`) falls back to the matching `AXONOPS_*` environment variable. Only the org
  is required: without `--cluster` the cluster list is read from `/api/v1/orgs` and
  every cluster of the organisation is exported, each with the type the API reports
  for it; credentials are optional too, so a self-hosted instance with authentication
  disabled is exported without sending an `Authorization` header. Every export also
  writes the matching CLI settings into `exports/<org>/`: a `.env.axonops` with the
  connection variables (the token and the password are left as commented
  placeholders — no credential is written to disk) and an `<org>.sh` replaying the
  configuration through `axonopscli`. Sections the CLI cannot set yet are listed as a
  TODO comment in the script.

- **CLI `health` command**: reports the health of every cluster visible to the
  organisation. A new `Orgs` component queries `/api/v1/orgs` and flattens the
  returned org / type / cluster tree, mapping status `0`/`1`/`2` to
  `OK`/`Warning`/`Error` (anything else is `Unknown`). By default only the
  clusters that are not OK are printed; `--show-healthy` also lists the healthy
  clusters and the nodes of `--cluster`, and `--show-orgs` lists the visible
  organisations. The command exits `1` when any cluster is not OK, so it can be
  used as a check in a script or a CI job.

### Changed

- **CLI**: `--help` now describes the tool as the "AxonOps CLI" rather than the
  "AxonOps Adaptive Repair CLI", which no longer covered what it does.

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
