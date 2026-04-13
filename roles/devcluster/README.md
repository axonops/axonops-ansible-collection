# devcluster Role

Deploys a complete AxonOps monitoring stack as Docker Compose services for development and demo use.

The stack runs OpenSearch (metrics backend), axon-server, axon-dash, and one to three Cassandra nodes with the AxonOps agent pre-baked into the Cassandra image. The role renders a `docker-compose.yml` from a Jinja2 template, writes a systemd oneshot service unit that wraps `docker compose up/down`, and optionally starts the stack immediately.

> **Warning:** This role is not suitable for production use. It disables OpenSearch security, uses default credentials, and is sized for a single-host development environment.

## Requirements

- **Docker CE with the Compose v2 plugin** MUST be installed and running on the target host before this role executes. The Compose v2 plugin is required — `docker-compose` (v1, standalone binary) is not supported.
- Set `devcluster_install_docker: true` to install Docker automatically using the `axonops.axonops.docker` role. See [Dependencies](#dependencies).
- The target host MUST be `amd64` / `x86_64`. Container images are not published for ARM or other architectures. The role warns when a non-`x86_64` architecture is detected but does not abort.
- The role manages the systemd service unit as `root`. The connecting user MUST have `become: true` privileges on the target host.
- Ansible 2.12 or higher.
- The `community.docker` collection is required when `devcluster_registry_auth` is set (used for `docker login`). Install it with `ansible-galaxy collection install community.docker`.

## Role Variables

### State

| Variable | Default | Description |
|----------|---------|-------------|
| `devcluster_state` | `present` | Lifecycle state. `present` deploys the stack; `absent` stops the service, removes volumes, removes the systemd unit, and deletes the compose directory. Valid values: `present`, `absent`. |
| `devcluster_compose_dir` | `/opt/axonops-devcluster` | Directory on the target host where `docker-compose.yml` is rendered. Created when `devcluster_state: present`; removed when `devcluster_state: absent`. |

### OpenSearch

| Variable | Default | Description |
|----------|---------|-------------|
| `devcluster_opensearch_version` | `2.19.1` | OpenSearch image tag. Security is disabled; the node runs in single-node discovery mode. |
| `devcluster_opensearch_java_opts` | `-Xms512m -Xmx512m` | JVM heap settings passed to the OpenSearch container via `OPENSEARCH_JAVA_OPTS`. Increase if you run workloads larger than a few hundred megabytes of data. |

### AxonOps Server

| Variable | Default | Description |
|----------|---------|-------------|
| `devcluster_axon_server_version` | `latest` | Image tag for `axon-server`. Pin to a specific version (e.g. `1.0.42`) to prevent unexpected upgrades when `devcluster_pull_policy: always`. |

### AxonOps Dash

| Variable | Default | Description |
|----------|---------|-------------|
| `devcluster_axon_dash_version` | `latest` | Image tag for `axon-dash`. |
| `devcluster_axon_dash_port` | `3000` | Host port mapped to the `axon-dash` container. Access the UI at `http://<host>:<port>`. Valid range: `1`–`65535`. |

### Cassandra

| Variable | Default | Description |
|----------|---------|-------------|
| `devcluster_cassandra_version` | `5.0` | Cassandra major version to deploy. Valid values: `5.0`, `4.1`, `4.0`. The role fails immediately if an unsupported value is supplied. |
| `devcluster_cassandra_nodes` | `1` | Number of Cassandra containers to start. Valid range: `1`–`3`. Nodes start sequentially via a `depends_on` chain; each node waits for the previous one to be healthy before starting. |
| `devcluster_cassandra_cluster_name` | `axonops-devcluster` | Cassandra cluster name passed to each container. Change this if you run multiple devcluster instances on the same host. |

### AxonOps Agent

| Variable | Default | Description |
|----------|---------|-------------|
| `devcluster_axonops_org` | `demo` | Organisation name shown in the AxonOps UI. This value is used to identify the cluster in axon-server. |

### Registry

| Variable | Default | Description |
|----------|---------|-------------|
| `devcluster_registry` | `registry.axonops.com/axonops-public/axonops-docker` | Base container registry path. All AxonOps images are pulled from this registry. |
| `devcluster_pull_policy` | `always` | Docker image pull policy passed to `docker compose up --pull`. `always` ensures the latest images are used on every run. `missing` skips pulls when the image is already present locally. `never` disables pulls entirely (offline use). |
| `devcluster_registry_auth` | `{}` | Optional registry credentials. When non-empty, the role runs `docker login` before pulling images. Provide `registry`, `username`, and `password` keys. Store `password` with Ansible Vault — the task runs with `no_log: true`. |

### Docker

| Variable | Default | Description |
|----------|---------|-------------|
| `devcluster_install_docker` | `false` | When `true`, the role includes `axonops.axonops.docker` before deploying the stack. Set this when the target host does not already have Docker installed. |

### Service Control

| Variable | Default | Description |
|----------|---------|-------------|
| `devcluster_service_name` | `axonops-devcluster` | Name of the systemd service unit. Change this if you run multiple devcluster instances on the same host. |
| `devcluster_start_on_install` | `true` | When `true`, the systemd service is enabled and started after the unit file is deployed. Set to `false` to render all files without starting the service — useful in CI environments where systemd is not available as PID 1. |

## Removal / Teardown

Set `devcluster_state: absent` to fully remove the stack from the target host. The role performs these steps in order:

1. Stops and disables the systemd service unit.
2. Runs `docker compose down --volumes` to remove containers and all Docker volumes (all stored data is deleted).
3. Removes the systemd unit file from `/etc/systemd/system/`.
4. Reloads the systemd daemon.
5. Removes `devcluster_compose_dir` and all its contents.

> **Warning:** `devcluster_state: absent` destroys all data stored in Docker volumes, including Cassandra data and OpenSearch indices. This is not reversible.

```yaml
- name: Remove AxonOps devcluster
  hosts: devbox
  become: true

  roles:
    - role: axonops.axonops.devcluster
      vars:
        devcluster_state: absent
```

## Dependencies

### Role dependency

This role has one optional role dependency: `axonops.axonops.docker`.

When `devcluster_install_docker: true`, the role includes `axonops.axonops.docker` automatically at the start of the task list. No explicit role dependency entry is required in your playbook.

When `devcluster_install_docker: false` (the default), you MUST ensure Docker CE and the Compose v2 plugin are installed on the target host by another means before running this role.

### Collection dependency

When `devcluster_registry_auth` is set to a non-empty value, the role uses `community.docker.docker_login` to authenticate to the registry. Install the collection before running the role in that case:

```bash
ansible-galaxy collection install community.docker
```

No collection dependency is needed when `devcluster_registry_auth` is left at its default empty value (`{}`).

## Example Playbooks

### Single-Node Stack (Quickstart)

One Cassandra node with default settings. The play completes once the systemd service unit has been started. The containers continue their startup sequence in the background — allow up to two minutes for all healthchecks to pass before accessing the UI at `http://<host>:3000`.

```yaml
- name: Deploy AxonOps devcluster
  hosts: devbox
  become: true

  roles:
    - role: axonops.axonops.devcluster
```

### Single-Node Stack with Docker Installation

Use this when the target host does not already have Docker installed.

```yaml
- name: Deploy AxonOps devcluster with Docker
  hosts: devbox
  become: true

  vars:
    devcluster_install_docker: true

  roles:
    - role: axonops.axonops.devcluster
```

### Three-Node Cassandra Cluster

Starts three Cassandra nodes in sequence. Each node waits for the previous one to pass its healthcheck before starting. Allow several minutes for the cluster to fully form.

```yaml
- name: Deploy AxonOps devcluster with 3 Cassandra nodes
  hosts: devbox
  become: true

  vars:
    devcluster_cassandra_nodes: 3
    devcluster_cassandra_version: "5.0"
    devcluster_cassandra_cluster_name: "axonops-demo"
    devcluster_axonops_org: "my-org"
    devcluster_axon_dash_port: 3000

  roles:
    - role: axonops.axonops.devcluster
```

### Pinned Versions with Registry Authentication

Use when pulling from a private registry or pinning to specific releases.

```yaml
- name: Deploy AxonOps devcluster with pinned versions
  hosts: devbox
  become: true

  vars:
    devcluster_axon_server_version: "1.0.42"
    devcluster_axon_dash_version: "1.0.42"
    devcluster_opensearch_version: "2.19.1"
    devcluster_pull_policy: missing
    devcluster_registry_auth:
      registry: registry.axonops.com
      username: "{{ vault_registry_username }}"
      password: "{{ vault_registry_password }}"

  roles:
    - role: axonops.axonops.devcluster
```

### Deploy Files Without Starting the Service

Set `devcluster_start_on_install: false` to render the compose file and systemd unit without starting anything. Start the service manually later with `systemctl start axonops-devcluster`.

```yaml
- name: Stage AxonOps devcluster without starting
  hosts: devbox
  become: true

  vars:
    devcluster_start_on_install: false

  roles:
    - role: axonops.axonops.devcluster
```

## Port Reference

| Service | Port | Host-exposed | Configurable |
| ------- | ---- | ------------ | ------------ |
| AxonOps Dash (web UI) | `3000` | Yes | Yes — `devcluster_axon_dash_port` |
| OpenSearch HTTP API | `9200` | No | No |
| axon-server HTTP | `8080` | No | No |
| axon-server agent gRPC | `1888` | No | No |
| Cassandra CQL | `9042` | No | No |

Only `devcluster_axon_dash_port` is mapped to the host. All other ports are internal to the Docker Compose network and cannot be reached from the host directly.

## Notes and Limitations

- **amd64 / x86_64 only.** All AxonOps container images are built for `linux/amd64`. Running on ARM64 (e.g. Apple Silicon, AWS Graviton) requires Rosetta 2 or hardware emulation and is not supported. The role warns but does not abort when a non-`x86_64` architecture is detected.

- **Development and demo use only.** OpenSearch runs with security disabled. There is no authentication on the AxonOps UI. Do not expose the host ports to untrusted networks.

- **Compose v2 required.** The systemd unit calls `/usr/bin/docker compose` (subcommand). The legacy `docker-compose` binary is not supported. Verify with `docker compose version`.

- **Sequential node startup.** The first Cassandra node waits for `axon-server` to be healthy before starting. Each additional Cassandra node then waits for the previous node to be healthy. Full cluster formation takes longer than a single-node deployment. Do not reduce `devcluster_cassandra_nodes` on a running stack without first draining data — the `absent` teardown path removes all volumes.

- **Stopping the service does not delete data.** Running `systemctl stop axonops-devcluster` runs `docker compose down`, which stops and removes the containers but preserves all Docker volumes (Cassandra data and OpenSearch indices). Data is only permanently deleted when `devcluster_state: absent` is applied, which runs `docker compose down --volumes`.

- **`devcluster_start_on_install: false` for CI.** Molecule tests and other CI environments typically run containers without systemd as PID 1. Set `devcluster_start_on_install: false` in those environments to verify file rendering without attempting to manage the service.

- **Image pull on every run.** The default `devcluster_pull_policy: always` causes Docker to check for updated images each time `systemctl start axonops-devcluster` runs. Set `devcluster_pull_policy: missing` to skip pulls when the image is already present, which is faster in offline or bandwidth-constrained environments.

## License

See the main collection `LICENSE` file.

## Author

AxonOps Limited
