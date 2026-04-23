# axonops-ansible-collection - CLAUDE.md

## Project Overview

Ansible collection (`axonops.axonops`) for installing and managing AxonOps components and the data infrastructure they monitor — primarily Apache Cassandra, Apache Kafka, and OpenSearch. Used by both the AxonOps team and customers for production deployments. Published to Ansible Galaxy.

## Current Status
- **Last Updated**: 2026-04-12
- **Current Phase**: Active development — roles being added and hardened
- **Health**: Green — 13 roles across Cassandra, Kafka, OpenSearch, Kubernetes, Docker, and AxonOps components

## Workflow — Agent Gates

These agents are mandatory gates, not optional tools. Do not skip them.

### Before creating any GitHub issue:

Run the **issue-writer** agent. Every issue must have: summary, detailed requirements, numbered acceptance criteria, specific testing requirements (named tests, not "add tests"), documentation requirements, dependencies, and labels. If any section is missing or vague, rewrite it before creating.

### Before creating any pull request:

Run the **docs-writer** agent to update role READMEs, examples, and any user-facing documentation affected by the change. A PR must not be created until documentation is current.

When a new role is added or an existing role is renamed/removed, `README.md` (root) MUST be updated to list it under the correct section in the **Role Documentation** table. The `docs/roles/README.md` index must also be kept in sync.

### After completing any feature:

1. **code-reviewer** — on all changed role files
2. **security-reviewer** — on any tasks touching TLS, credentials, or external input
3. **docs-writer** — update role READMEs and user-facing docs before opening the PR
4. **docs-quality-reviewer** — final review of any README or docs changes

### When writing or reviewing documentation:

5. **ansible-devops-reviewer** is the main writer and owner
6. **docs-quality-reviewer** — for role READMEs, examples, and user-facing docs

## Active Tasks

1. [COMPLETE] OpenSearch role: group name hardcoded to `groups['opensearch']`
   - Fixed: template now uses `ansible_play_hosts` as the default for `opensearch_seed_hosts` and `opensearch_initial_cluster_manager_nodes`

2. [COMPLETE] OpenSearch role: additional system tuning
   - Added `vm.swappiness`, `net.ipv4.tcp_retries2`, and THP disabling to `tune.yml`

3. [COMPLETE] OpenSearch molecule CI: systemd not available in Docker containers
   - Fixed: `opensearch_start_on_install: false` in converge.yml; service start tasks are all guarded by `when: opensearch_start_on_install`

4. [IN PROGRESS] OpenSearch README
   - Comprehensive user-focused README written by docs-quality-reviewer; committed as `9e4385b`

## Recent Progress (2026-03 to 2026-04)

- Added `opensearch` role: tar-based install, security plugin, TLS (generate or custom mode), system tuning, multi-node support (`feat: add opensearch role`, PR #61)
- Added `k8ssandra` role: Helm-based cert-manager + k8ssandra operator install, K8ssandraCluster CRD with AxonOps sidecar images, molecule tests
- Added `strimzi` role: Helm-based Strimzi operator install, KafkaNodePool CRD, KRaft mode only (no ZooKeeper), molecule tests (PR #60)
- Added path filters to all GitHub Actions molecule workflows to reduce CI blast radius
- Fixed `cassandra` role: block/rescue install logic now retries with archive URL on any error (including 404)
- Fixed `cassandra` role: cluster_type default corrected (PR #57)
- Added healthcheck CLI support (PR #58)

## Architecture & Key Decisions

- **Collection**: `axonops.axonops`, version `0.5.0`, Apache-2.0
- **Role pattern**: `defaults/main.yml` (all variables with sensible defaults), `tasks/main.yml` (orchestrator importing subtask files), `templates/` (Jinja2 for config files), `molecule/default/` (Docker-based tests)
- **Molecule driver**: Docker with `geerlingguy/docker-*-ansible` images (no systemd as PID 1 — skip service start tasks in converge with `opensearch_start_on_install: false` or equivalent)
- **Kubernetes roles** (`k8ssandra`, `strimzi`): Helm install only — does not use `kubernetes.core.k8s` directly, installs operators via Helm and applies CRs via templates + `kubectl apply`
- **OpenSearch TLS**: two modes — `generate` (default, uses searchguard-tlstool to create self-signed certs) and `custom` (user supplies cert paths on control node)
- **Cassandra install**: tar-based from Apache mirrors; falls back to `cassandra_archive_url` on any download error

## Roles

| Role | Purpose | Molecule |
| --- | --- | --- |
| `agent` | AxonOps agent (Cassandra/Kafka monitoring sidecar) | ✅ |
| `cassandra` | Apache Cassandra install + configuration (tar) | ✅ |
| `configurations` | AxonOps configuration resources (alerts, silences) | ✅ |
| `cqlai` | CQL AI assistant component | ✅ |
| `dash` | AxonOps dashboard web UI | ✅ |
| `elastic` | Elasticsearch backend for AxonOps server | ✅ |
| `java` | Java (JDK) install helper | ✅ |
| `k8ssandra` | K8ssandra operator + K8ssandraCluster CR (Kubernetes) | ✅ |
| `opensearch` | OpenSearch cluster install + security + tuning | ✅ |
| `operator` | AxonOps Kubernetes operator install + AxonOpsPlatform CR (Kubernetes) | ✅ |
| `devcluster` | Docker Compose-based AxonOps dev/demo stack (OpenSearch + server + dash + Cassandra) | ✅ |
| `preflight` | Pre-flight checks (OS, Java, disk) | — |
| `server` | AxonOps server (axon-server) | ✅ |
| `strimzi` | Strimzi operator + Kafka/KafkaNodePool CR (Kubernetes) | ✅ |

## Dependencies & Integration Points

- **Ansible Galaxy collections required**: `ansible.posix`, `community.general`, `kubernetes.core` (for k8ssandra/strimzi)
- **External tools**: `searchguard-tlstool` (downloaded at runtime for OpenSearch TLS generation), Helm (for k8ssandra and strimzi)
- **AxonOps server**: agent, dash, and configurations roles depend on a running AxonOps server
- **GitHub repo**: `axonops/axonops-ansible-collection`

## Useful Commands

```bash
# Install collection locally for development
ansible-galaxy collection install . --force

# Run molecule tests for a role
cd roles/<role_name>
molecule test

# Run only specific molecule stages
molecule converge
molecule verify
molecule destroy

# Install collection dependencies
ansible-galaxy collection install -r requirements.yml

# Run a playbook with the collection installed locally
ansible-playbook examples/opensearch.yml -i inventory/hosts

# Lint all YAML
ansible-lint
```

## Known Limitations & Tech Debt

- **OpenSearch group name**: templates default to `ansible_play_hosts` — works when all hosts in the play are OpenSearch nodes; for mixed-role plays, override `opensearch_seed_hosts` and `opensearch_initial_cluster_manager_nodes` explicitly
- **Kubernetes roles not idempotent on CRs**: k8ssandra and strimzi CR apply uses `kubectl apply` which is idempotent, but Helm upgrades may not detect all changes without `--force`
- **Strimzi KRaft only**: no ZooKeeper mode supported — Strimzi 0.51+ only
- **OpenSearch `generate` TLS mode**: searchguard-tlstool is downloaded at runtime; needs internet access on control node
- **No integration tests**: molecule tests verify task execution but don't test actual service functionality (no real cluster started in CI)
- **Cassandra version pinned to 5.x in k8ssandra role**: K8ssandraCluster CRD images use `ghcr.io/axonops/k8ssandra/cassandra:5.x` — Cassandra 4.x not supported

## Next Steps & Roadmap

1. Verify opensearch molecule CI passes cleanly after recent fixes
2. Add `examples/opensearch-custom-tls.yml` example playbook
3. Consider a `healthcheck` role or extend `configurations` to cover more AxonOps operational resources
4. Publish updated collection to Ansible Galaxy (bump version in `galaxy.yml`)
5. Add `CONTRIBUTING.md` documenting role patterns and molecule requirements
