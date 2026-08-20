<a href="https://axonops.com"><img src="https://digitalis-marketplace-assets.s3.us-east-1.amazonaws.com/AxonopsDigitalMaster_AxonopsFullLogoBlue.jpg" alt="AxonOps" height="60"></a>

# AxonOps Ansible Execution Environment

An [Ansible Execution Environment](https://ansible.readthedocs.io/projects/builder/) image that bundles the `axonops.axonops` collection and everything it needs to talk to an AxonOps server, so a container can run any playbook of this collection without downloading anything at start-up.

Published image: **`ghcr.io/axonops/axonops-ansible-ee`**

## What it is

It is a runtime, not a task. The image carries `ansible-core`, this collection and its dependencies — no baked-in playbook, no one-shot bootstrap behaviour and deliberately no entrypoint of its own. `docker run` with no command drops you at a shell; give it a command to run something:

```bash
docker run --rm \
  -e AXONOPS_URL -e AXONOPS_ORG -e AXONOPS_CLUSTER \
  ghcr.io/axonops/axonops-ansible-ee:latest \
  ansible-playbook /work/my-playbook.yml
```

One generic image serves every consumer. Playbooks shipped in the collection's `playbooks/` directory are runnable by FQCN (`ansible-playbook axonops.axonops.<playbook>`), so a one-shot bootstrap container is a command, not a second image.

## Quick start

Pull and inspect the published image:

```bash
docker pull ghcr.io/axonops/axonops-ansible-ee:latest
docker run --rm ghcr.io/axonops/axonops-ansible-ee:latest ansible --version
docker run --rm ghcr.io/axonops/axonops-ansible-ee:latest ansible-galaxy collection list
```

Prove the image is self-contained — this must succeed with networking disabled:

```bash
docker run --rm --network none ghcr.io/axonops/axonops-ansible-ee:latest \
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
  --tag ghcr.io/axonops/axonops-ansible-ee:local \
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
  -t ghcr.io/axonops/axonops-ansible-ee:local \
  ci/execution-environment/_context

# Build and push both architectures
docker buildx build --platform linux/amd64,linux/arm64 --push \
  --provenance=false \
  --build-arg PYCMD=/usr/bin/python3.12 \
  -f ci/execution-environment/_context/Containerfile \
  -t ghcr.io/axonops/axonops-ansible-ee:vX.Y.Z \
  ci/execution-environment/_context
```

The generated build context under `ci/execution-environment/_context/` is disposable and is not committed.

To build a different release of the collection, change `version:` in [`requirements.yml`](requirements.yml) to the git tag you want, or pass the tag to the `workflow_dispatch` trigger in CI.

## Cutting a release

Cutting a release is just pushing a `v*` git tag — no version bump is prepared by hand. The tag build bakes in the collection at that same tag, and the release workflow commits the matching `version:` in [`requirements.yml`](requirements.yml) and `galaxy.yml` back to the default branch, so what is committed always names the last release.

An image published under a release tag therefore contains that tag of the collection by construction: the pin the build uses is the tag being built, not whatever happened to be committed when the tag was cut. Manual `workflow_dispatch` builds override the pin with the ref they are given — that is what they are for — and in exchange they are refused an image tag starting `v` followed by a digit, so a hand-built image can never occupy a release tag.

## What is in the image

| Component | Pinned to | Defined in |
| --- | --- | --- |
| Base image | `quay.io/centos/centos:stream9`, by manifest digest, plus `python3.12` | `execution-environment.yml` |
| `ansible-core` | `2.18.4` | `execution-environment.yml` |
| `ansible-runner` | `2.4.1` | `execution-environment.yml` |
| `axonops.axonops` collection | An explicit git tag of this repository | `requirements.yml` |
| Collections the roles call | `ansible.posix`, `community.general`, `community.crypto`, `community.docker`, `kubernetes.core` | `requirements.yml`, and `dependencies:` in `galaxy.yml` |
| Python runtime dependencies | Exact versions | `requirements.txt` |
| System packages | `git-core` plus the build toolchain | `bindep.txt` |

The collection is installed from a git tag rather than from Ansible Galaxy so the image can be built for a release tag without waiting for the Galaxy publish to complete.

The collections the roles call are declared twice on purpose: as `dependencies:` in the
repository-root `galaxy.yml`, so a plain `ansible-galaxy collection install axonops.axonops`
pulls them on any control node, and again in `requirements.yml`, so the image contents do not
depend on the dependency-resolution behaviour of whichever `ansible-galaxy` version
`ansible-builder` runs. Adding a collection to a role means updating both.

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
  axonops-bootstrap:
    image: ghcr.io/axonops/axonops-ansible-ee:vX.Y.Z
    command: ["ansible-playbook", "axonops.axonops.alert_bootstrap"]
    environment:
      AXONOPS_URL: http://axon-server:8080
      AXONOPS_ORG: example
```

The `alert_bootstrap` playbook above is the one being added in [#130](https://github.com/axonops/axonops-ansible-collection/issues/130); it does not exist yet.

## Contact

Maintained by [AxonOps](https://axonops.com). For support, get in touch at [axonops.com/contact](https://axonops.com/contact).

Licensed under the Apache License 2.0.
