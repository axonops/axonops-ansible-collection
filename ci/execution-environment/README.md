<a href="https://axonops.com"><img src="https://digitalis-marketplace-assets.s3.us-east-1.amazonaws.com/AxonopsDigitalMaster_AxonopsFullLogoBlue.jpg" alt="AxonOps" height="60"></a>

# AxonOps Alert Bootstrap Execution Environment

An [Ansible Execution Environment](https://ansible.readthedocs.io/projects/builder/) image that bundles the `axonops.axonops` collection and everything it needs to talk to an AxonOps server, so a container can apply AxonOps configuration without downloading anything at start-up.

Published image: **`ghcr.io/axonops/axonops-alert-bootstrap-ee`**

## Current status

The image ships `ansible-core`, the collection and its dependencies — nothing else. It has no bootstrap playbook and no entrypoint of its own yet, so `docker run` drops you at a shell rather than applying any alert rules.

The default alert-rule profile and the bootstrap playbook that consumes it land in [#130](https://github.com/axonops/axonops-ansible-collection/issues/130); `execution-environment.yml` marks the single place they plug in. Until then the image is useful as a ready-made runtime for playbooks you mount in yourself.

## Quick start

Pull and inspect the published image:

```bash
docker pull ghcr.io/axonops/axonops-alert-bootstrap-ee:latest
docker run --rm ghcr.io/axonops/axonops-alert-bootstrap-ee:latest ansible --version
docker run --rm ghcr.io/axonops/axonops-alert-bootstrap-ee:latest ansible-galaxy collection list
```

Prove the image is self-contained — this must succeed with networking disabled:

```bash
docker run --rm --network none ghcr.io/axonops/axonops-alert-bootstrap-ee:latest \
  ansible-galaxy collection list
```

## Build it locally

Requirements:

- A container runtime — Docker, or Podman with `--container-runtime podman`.
- `ansible-builder` 3.1.0: `pip install 'ansible-builder==3.1.0'`

From the root of this repository:

```bash
ansible-builder build \
  --file ci/execution-environment/execution-environment.yml \
  --context ci/execution-environment/_context \
  --output-filename Containerfile \
  --build-arg PYCMD=/usr/bin/python3.12 \
  --tag ghcr.io/axonops/axonops-alert-bootstrap-ee:local \
  -v 3
```

`--output-filename Containerfile` matches what CI generates. Without it the file is named after whichever runtime `ansible-builder` detects locally — `Dockerfile` for Docker, `Containerfile` for Podman — so pinning it keeps the local and CI builds operating on identically named files.

`PYCMD` is required: the base image's default `python3` is 3.9, and `ansible-core` 2.18 needs 3.11 or newer, so the build runs against the `python3.12` installed into the base stage.

`ansible-builder build` leaves the image in the Buildx cache. To get a runnable local image, or to build for several architectures at once, build the generated context directly:

```bash
# Load a single-architecture image into the local Docker daemon
docker buildx build --load \
  --build-arg PYCMD=/usr/bin/python3.12 \
  -f ci/execution-environment/_context/Containerfile \
  -t ghcr.io/axonops/axonops-alert-bootstrap-ee:local \
  ci/execution-environment/_context

# Build and push both architectures
docker buildx build --platform linux/amd64,linux/arm64 --push \
  --provenance=false \
  --build-arg PYCMD=/usr/bin/python3.12 \
  -f ci/execution-environment/_context/Containerfile \
  -t ghcr.io/axonops/axonops-alert-bootstrap-ee:vX.Y.Z \
  ci/execution-environment/_context
```

The generated build context under `ci/execution-environment/_context/` is disposable and is not committed.

To build a different release of the collection, change `version:` in [`requirements.yml`](requirements.yml) to the git tag you want, or pass the tag to the `workflow_dispatch` trigger in CI.

## What is in the image

| Component | Pinned to | Defined in |
| --- | --- | --- |
| Base image | `quay.io/centos/centos:stream9`, by manifest digest, plus `python3.12` | `execution-environment.yml` |
| `ansible-core` | `2.18.4` | `execution-environment.yml` |
| `ansible-runner` | `2.4.1` | `execution-environment.yml` |
| `axonops.axonops` collection | An explicit git tag of this repository | `requirements.yml` |
| Python runtime dependencies | Exact versions | `requirements.txt` |
| System packages | `git-core` plus the build toolchain | `bindep.txt` |

The collection is installed from a git tag rather than from Ansible Galaxy so the image can be built for a release tag without waiting for the Galaxy publish to complete.

The Python dependencies here are the runtime subset only. The repository-root `requirements.txt` also carries development tooling (`ansible-lint`, `black`, `pylint`, `yamllint`), which has no place in a runtime image.

## Published tags

| Trigger | Tags pushed |
| --- | --- |
| Git tag `vX.Y.Z` | `:vX.Y.Z` and `:latest`, both resolving to the same digest |
| `workflow_dispatch` | The tag given as input; `:latest` only if the `update_latest` input is set |
| Pull request | Nothing — the image is built to validate the definition, then discarded |

Images are built for `linux/amd64` and `linux/arm64`. Every run — pull requests included — builds the native image first and asserts that `ansible-galaxy collection list` finds `axonops.axonops` with `--network none`, so a build that quietly stopped being self-contained fails before anything is published.

Reference a specific version from a consumer (for example a Docker Compose stack in `axonops-containers`) rather than `:latest`, so that stack's behaviour does not change under it:

```yaml
services:
  axonops-alert-bootstrap:
    image: ghcr.io/axonops/axonops-alert-bootstrap-ee:v0.6.3
```

## Contact

Maintained by [AxonOps](https://axonops.com). For support, get in touch at [axonops.com/contact](https://axonops.com/contact).

Licensed under the Apache License 2.0.
