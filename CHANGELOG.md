# Changelog

All notable changes to this collection are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **cassandra**: JKS keystore/truststore passwords are now externalised to
  `keystore_password_file:` / `truststore_password_file:` references in
  `cassandra.yaml` by default. Each password is written to a separate mode
  `0600` file owned by the cassandra user under `cassandra_conf_dir`, covering
  both `server_encryption_options` and `client_encryption_options`. Set
  `cassandra_use_password_files: false` to restore the previous inline
  behaviour. See [docs/roles/cassandra.md](docs/roles/cassandra.md#password-files-default).
  ([#99](https://github.com/axonops/axonops-ansible-collection/issues/99))

### Fixed

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
