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

### Fixed

- **cassandra**: `cassandra_use_password_files` no longer breaks Cassandra
  startup. The `keystore_password_file:` / `truststore_password_file:` keys it
  emitted were added in Apache Cassandra 6.0 (CASSANDRA-13428) and do not exist
  in 4.1.x / 5.0.x, the only versions this role supports — Cassandra rejected
  them with `Invalid yaml. Please remove properties [...]` and refused to boot.
  The feature now defaults to `false` and is force-disabled with a warning if
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
