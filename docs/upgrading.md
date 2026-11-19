# Upgrading Existing Deployments

How to change the version of Cassandra, OpenSearch or Kafka on a running cluster without an outage.

The roles install the new version and restart the service. They do not coordinate between nodes, so a cluster upgrade is a rolling upgrade driven by your playbook: one node at a time, with a health check before moving on.

## Principles

| Rule | Why |
|------|-----|
| One node at a time (`serial: 1`) | The rest of the cluster keeps serving while a node is down |
| Check health before the next node | A second node going down while the first is still recovering causes the outage you are avoiding |
| `any_errors_fatal: true` | Stops the whole play on the first failure instead of moving on to the next node |
| Back up first | Snapshot data and keep a copy of the configuration before touching production |
| One major version at a time | Skipping major versions is not supported by the upstream projects |
| Read the upstream release notes | Breaking changes and removed settings are not handled by the roles |
| Test on a non-production cluster first | Same version path, same variables |

Do not run an upgrade play with `--tags` that skips the install tasks, and do not change unrelated variables in the same run.

## Rolling upgrade pattern

```yaml
- name: Rolling upgrade
  hosts: opensearch          # the group for the component being upgraded
  become: true
  serial: 1
  any_errors_fatal: true
  pre_tasks:
    - name: Check the cluster is healthy before touching this node
      ansible.builtin.debug:
        msg: "Replace with the health check for the component, see the sections below"
  roles:
    - role: axonops.axonops.opensearch
      vars:
        opensearch_version: "3.9.0"
        # plus your existing variables
  post_tasks:
    - name: Wait until the node is healthy again
      ansible.builtin.debug:
        msg: "Replace with the health check for the component, see the sections below"
```

Keep your existing inventory variables. Change only the version variable.

## OpenSearch

### What the role does

When `opensearch_version` is newer than the installed version, the role:

1. Stops the service.
2. Copies `config/` to `<opensearch_install_root>/config.pre-upgrade-<old version>/` (mode `0700`, kept after the upgrade, one per upgrade).
3. Replaces everything in the install directory except `config`, `data` and `logs`.
4. Reinstalls the snapshot repository plugin when `opensearch_snapshot_enabled` is `true`.
5. Starts the service, or restarts it through the handler when `opensearch_start_on_install` is `false` and the service was running.

If a step fails, the role restores the previous distribution, restarts the service if it was running, and fails. Downgrades fail with a message naming both versions.

### What you must do

The role does not touch shard allocation and does not wait for cluster health.

Before upgrading each node, restrict allocation to primaries and flush so the cluster does not start moving shards while the node is down:

```yaml
  pre_tasks:
    - name: Restrict shard allocation to primaries
      ansible.builtin.uri:
        url: "https://{{ opensearch_network_host }}:9200/_cluster/settings"
        method: PUT
        user: admin
        password: "{{ opensearch_admin_password }}"
        force_basic_auth: true
        validate_certs: false
        body_format: json
        body:
          persistent:
            cluster.routing.allocation.enable: primaries
      delegate_to: localhost
      become: false

    - name: Flush indices
      ansible.builtin.uri:
        url: "https://{{ opensearch_network_host }}:9200/_flush"
        method: POST
        user: admin
        password: "{{ opensearch_admin_password }}"
        force_basic_auth: true
        validate_certs: false
      delegate_to: localhost
      become: false
```

After the role has run on the node, re-enable allocation and wait for green:

```yaml
  post_tasks:
    - name: Re-enable shard allocation
      ansible.builtin.uri:
        url: "https://{{ opensearch_network_host }}:9200/_cluster/settings"
        method: PUT
        user: admin
        password: "{{ opensearch_admin_password }}"
        force_basic_auth: true
        validate_certs: false
        body_format: json
        body:
          persistent:
            cluster.routing.allocation.enable: null
      delegate_to: localhost
      become: false

    - name: Wait for green cluster health
      ansible.builtin.uri:
        url: "https://{{ opensearch_network_host }}:9200/_cluster/health?wait_for_status=green&timeout=60s"
        user: admin
        password: "{{ opensearch_admin_password }}"
        force_basic_auth: true
        validate_certs: false
      delegate_to: localhost
      become: false
      register: _health
      until: _health.status == 200
      retries: 20
      delay: 15
```

Use `http://` and drop the credentials when `opensearch_security_enabled` is `false`. Replace `validate_certs: false` with your CA when you use custom TLS certificates.

### Things to know

- The new release's default configuration files are not applied. Compare the backup with the release notes and merge changes by hand.
- Third-party plugins are removed with `plugins/` and must be reinstalled. If you use `opensearch_snapshot_plugin_local_archive`, it must match the new `opensearch_version`.
- Single-node clusters have no replicas to fall back on, so the node is offline while the upgrade runs.
- Security certificates, internal users and the security index are kept. The role does not re-run `securityadmin` for an upgrade.

## Cassandra

### What the role does

With `cassandra_install_format: tar`, a new `cassandra_version` is extracted to its own `apache-cassandra-<version>` directory and the `cassandra_home_dir` symlink is pointed at it. The configuration is rendered for the new version and the service is restarted through the handler.

The role does not drain the node, wait for it to rejoin the ring, or run `nodetool upgradesstables`. Do those steps in your playbook.

### What you must do

Per node, in this order:

```yaml
  pre_tasks:
    - name: Drain the node
      ansible.builtin.command: nodetool drain
      changed_when: true
```

After the role has run on the node, wait for it to be up and normal:

```yaml
  post_tasks:
    - name: Wait for the node to report UN
      ansible.builtin.shell: >-
        set -o pipefail;
        nodetool status | grep -E "^UN\s+{{ ansible_default_ipv4.address }}\s"
      args:
        executable: /bin/bash
      register: _node_status
      until: _node_status.rc == 0
      retries: 30
      delay: 10
      changed_when: false
```

Once every node is on the new version, rewrite the SSTables on each node, one node at a time:

```bash
nodetool upgradesstables
```

### Things to know

- Upgrade one major version at a time and read the Cassandra `NEWS.txt` for the target version first.
- Do not change the schema, add or remove nodes, or run repairs while the cluster has mixed versions.
- Take a snapshot before starting: `nodetool snapshot -t pre-upgrade`.
- Rolling back after SSTables have been rewritten is not supported. Restore from the snapshot.
- For the `cassandra_data_directory` default change in 0.6.0, see "Upgrade Notes" in the [cassandra role README](../roles/cassandra/README.md).

## Kafka

### What the role does

The tar install extracts the new `kafka_version` to its own directory and updates the home symlink. The service is restarted through the handler. The role does not check broker or controller health between nodes.

### What you must do

- Upgrade one broker at a time and wait until there are no under-replicated partitions before moving on.
- For KRaft clusters, upgrade the controllers first, then the brokers, and finalise the metadata version at the end with `kafka-features.sh`.
- Follow the upgrade notes in the Apache Kafka documentation for the target version.

## Recovery after a failed upgrade

| Situation | What to do |
|-----------|------------|
| OpenSearch step failed, role restored the previous version | Read the failure message, fix the cause, re-run. The backup is in `config.pre-upgrade-<old version>/` |
| OpenSearch run interrupted (lost connection, killed play) | The role refuses to continue when `config/` exists but no core jar is found. Move the entries from `<opensearch_install_root>/.old-<old version>/` back into `<opensearch_install_root>/`, then re-run |
| Node does not rejoin after upgrade | Check the service log. Leave allocation restricted (OpenSearch) or the node drained (Cassandra) until it is healthy. Do not upgrade the next node |
| Need to go back to the old version | OpenSearch and Cassandra do not support downgrades once the data has been written by the new version. Restore from the pre-upgrade snapshot or backup |
