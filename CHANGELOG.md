# Changelog

All notable changes to this collection are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **kafka**: `kafka_listeners` now describes broker listeners as mappings with
  per-listener security, so one broker can serve endpoints with different
  settings — for example an internal SASL listener plus a TLS listener for
  external clients or a certificate scanner. Each entry takes `name`, `port`,
  and optional `tls`, `sasl`, `client_auth`, `advertised_host` and
  `advertised_port`; the security protocol is derived from `tls`/`sasl` by the
  same rule the role applies cluster-wide. TLS material is provisioned whenever
  any listener sets `tls: true`, so a TLS listener works with
  `kafka_tls_enabled: false`. `advertised.listeners`,
  `listener.security.protocol.map`, per-listener JAAS, firewall rules and
  generated certificate SANs are all built from the same list. New
  `kafka_tls_generate_key_type`, `kafka_tls_generate_key_size` and
  `kafka_tls_generate_extra_sans` tune the generated certificates. Covered by
  the new `listeners` molecule scenario.

### Changed

- **kafka**: `admin.properties` and the AxonOps agent client config now derive
  their security from whichever listener is bound to port 9092 — the port those
  clients bootstrap against — instead of the cluster-wide TLS/SASL flags. With
  a single derived listener the output is unchanged.

### Removed

- **kafka**: `kafka_listeners` no longer accepts bare strings
  (`"SASL_SSL://:9092"`). Use the mapping form; the role fails with a migration
  message if strings are found. Deployments that left `kafka_listeners` empty
  are unaffected and render byte-identical configuration.

### Fixed

- **kafka**: the self-signed CA in `generate` mode is no longer skipped when the
  first host in the play needs no TLS material. `run_once` tasks execute on the
  first host and evaluate their conditions against it, so in a play mixing
  controller-only nodes with brokers that have a TLS listener, the CA tasks were
  skipped for the entire play and per-host certificate generation then failed
  with "The directory ... does not exist". The CA tasks moved to `tls_ca.yml`
  and are guarded by a single play-wide condition,
  `kafka__tls_generate_anywhere`, which folds in both the TLS requirement and
  `kafka_tls_mode` so no per-host term remains. Note that `run_once` tasks also
  *read variables* from the first host: `kafka_tls_mode` and the
  `kafka_tls_generate_*` settings must be set play-wide, which is now documented
  in the role docs.

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
