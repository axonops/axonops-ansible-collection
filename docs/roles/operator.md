# Operator Role

## Overview

The `operator` role installs the AxonOps Kubernetes operator into a cluster via its OCI Helm chart. It optionally installs cert-manager as a prerequisite and can deploy one or more `AxonOpsPlatform` custom resources that bring up the full AxonOps server stack (axon-server, dashboard, timeseries database, and search).

The role runs entirely from the Ansible control node and targets the Kubernetes API server — it does not SSH into cluster nodes. All Kubernetes operations use the `kubernetes.core` collection.

## Requirements

- Ansible 2.10 or higher
- `kubernetes.core` collection version 3.0.0 or higher:
  ```bash
  ansible-galaxy collection install "kubernetes.core:>=3.0.0"
  ```
- `helm` CLI installed on the control node and reachable on `PATH`
- `kubectl` installed on the control node and configured with a kubeconfig that has cluster-admin access (required to install CRDs and create namespaces)
- A reachable Kubernetes API server — the active `kubectl` context is used unless overridden via `kubernetes.core` environment variables

For the integration test scenario (`molecule test`):

- [Kind](https://kind.sigs.k8s.io/docs/user/quick-start/) — the `default` scenario creates a local Kind cluster named `molecule-operator`

## How It Works

The role performs up to three steps, each independently controllable:

1. **cert-manager** — Installs via Helm with `crds.enabled: true` and waits for the `cert-manager-webhook` deployment to become ready before continuing
2. **AxonOps operator** — Installs the `axonops-operator` Helm chart and waits for the `axonops-operator-controller-manager` deployment to become ready
3. **AxonOpsPlatform CRs** — Deploys one CR per entry in `axonops_operator_platforms`

Steps can be skipped individually using variables or Ansible tags.

## Role Variables

### cert-manager

| Variable | Default | Description |
|----------|---------|-------------|
| `axonops_operator_install_cert_manager` | `true` | Install cert-manager via Helm before the operator. Set to `false` if cert-manager is already installed in the cluster |
| `axonops_operator_cert_manager_version` | `v1.20.1` | cert-manager Helm chart version to install |
| `axonops_operator_cert_manager_namespace` | `cert-manager` | Namespace into which cert-manager is installed. Created if it does not exist |
| `axonops_operator_cert_manager_chart` | `oci://quay.io/jetstack/charts/cert-manager` | OCI chart reference for cert-manager |

### AxonOps Operator

| Variable | Default | Description |
|----------|---------|-------------|
| `axonops_operator_install_operator` | `true` | Install the `axonops-operator` Helm chart |
| `axonops_operator_version` | `0.1.0` | Helm chart version to install |
| `axonops_operator_namespace` | `axonops-system` | Namespace into which the operator is installed. Created if it does not exist |
| `axonops_operator_chart` | `oci://ghcr.io/axonops/charts/axonops-operator` | OCI chart reference for the operator |
| `axonops_operator_helm_values` | `{}` | Arbitrary Helm values merged on top of the role's base values. Any key from the chart's `values.yaml` can be overridden here |
| `axonops_operator_wait` | `true` | Wait for the `axonops-operator-controller-manager` deployment to become ready before continuing |
| `axonops_operator_wait_timeout` | `300` | Maximum seconds to wait for the operator deployment to become ready. The role polls every 10 seconds |
| `axonops_operator_crd_install` | `true` | Install CRDs with the chart (`crd.enable`) |
| `axonops_operator_crd_keep` | `true` | Keep CRDs when the Helm release is uninstalled (`crd.keep`). Setting this to `false` causes all custom resources to be deleted when the chart is removed |

`axonops_operator_helm_values` is merged recursively with the role's base values using Ansible's `combine(..., recursive=true)` filter. The base values are:

```yaml
crd:
  enable: "{{ axonops_operator_crd_install }}"
  keep: "{{ axonops_operator_crd_keep }}"
```

Any key provided in `axonops_operator_helm_values` takes precedence over the base. Common overrides:

```yaml
axonops_operator_helm_values:
  manager:
    replicas: 2
  certManager:
    enable: true        # tell the operator to use cert-manager for its own webhook TLS
  operator:
    watchAllNamespaces: false
    watchNamespaces:
      - production
      - staging
```

See the [chart values reference](https://github.com/axonops/axonops-operator/blob/main/charts/axonops-operator/values.yaml) for the full list of available keys.

### AxonOpsPlatform CRs

| Variable | Default | Description |
|----------|---------|-------------|
| `axonops_operator_platforms` | `[]` | List of `AxonOpsPlatform` custom resources to deploy. Each entry creates one CR. When empty, the operator is installed but no platforms are deployed — the role emits a warning |

Each entry in `axonops_operator_platforms` MUST include `name` and `namespace`. The CR deployment mode is determined by which additional key is present:

| Entry field | Required | Description |
|-------------|----------|-------------|
| `name` | Yes | Name of the `AxonOpsPlatform` resource |
| `namespace` | Yes | Kubernetes namespace in which the CR is created. Created if it does not exist |
| `spec` | No | `AxonOpsPlatform` spec dict rendered by the role's template (simple mode) |
| `custom_spec` | No | Full resource manifest applied verbatim (custom mode). Takes precedence over `spec` when both are defined |
| `labels` | No | Key/value map of labels added to the CR metadata (simple mode only) |
| `annotations` | No | Key/value map of annotations added to the CR metadata (simple mode only) |

## AxonOpsPlatform CR

The role supports two modes for deploying `AxonOpsPlatform` resources. Choose based on how much control you need over the manifest.

### Simple mode (`spec`)

The role renders the `AxonOpsPlatform` CR from its internal template using the `spec` dict you provide. The template writes `apiVersion`, `kind`, and `metadata` automatically. Optional `labels` and `annotations` fields are also supported.

Use simple mode when you want Ansible to manage the boilerplate and you only need to supply the spec body.

```yaml
axonops_operator_platforms:
  - name: axonops
    namespace: axonops
    labels:
      environment: production
    spec:
      server:
        orgName: "ACME Corp"
      timeSeries: {}
      search: {}
      dashboard: {}
```

The rendered CR has the form:

```yaml
apiVersion: core.axonops.com/v1alpha1
kind: AxonOpsPlatform
metadata:
  name: axonops
  namespace: axonops
  labels:
    environment: production
spec:
  server:
    orgName: "ACME Corp"
  timeSeries: {}
  search: {}
  dashboard: {}
```

When `spec` is omitted or empty, the role renders `spec: {}`, which creates a minimal platform with operator defaults.

### Custom mode (`custom_spec`)

The role applies the `custom_spec` dict verbatim using `kubernetes.core.k8s`. The entire resource manifest — including `apiVersion`, `kind`, and `metadata` — is your responsibility. Use this mode when you need fields that the simple template does not support, or when you want to manage the full manifest in your playbook variables.

```yaml
axonops_operator_platforms:
  - name: axonops-prod
    namespace: axonops-prod
    custom_spec:
      apiVersion: core.axonops.com/v1alpha1
      kind: AxonOpsPlatform
      metadata:
        name: axonops-prod
        namespace: axonops-prod
        annotations:
          managed-by: ansible
      spec:
        server:
          orgName: "ACME Corp"
          replicas: 3
        timeSeries:
          replicas: 3
          storage:
            size: "500Gi"
            storageClassName: fast-ssd
        search:
          replicas: 2
          storage:
            size: "250Gi"
            storageClassName: fast-ssd
        dashboard:
          replicas: 2
```

When `custom_spec` is defined, `spec`, `labels`, and `annotations` on the same entry are ignored.

## Dependencies

This role has no Ansible role dependencies. It requires the `kubernetes.core` collection:

```bash
ansible-galaxy collection install "kubernetes.core:>=3.0.0"
```

`helm` and `kubectl` must be installed on the control node. The role does not install them.

## Example Playbooks

### Minimal — operator only

Installs the operator without cert-manager and without deploying any platform. Use this when cert-manager is already present in the cluster and you want to install the operator in isolation before defining platforms separately.

```yaml
- name: Install AxonOps operator
  hosts: localhost
  connection: local
  gather_facts: false

  roles:
    - role: axonops.axonops.operator
      vars:
        axonops_operator_install_cert_manager: false
        axonops_operator_install_operator: true
        axonops_operator_platforms: []
```

### Standard — cert-manager and operator

Installs cert-manager then the operator with cert-manager integration enabled. No platforms are deployed; this is the typical first step for a new cluster.

```yaml
- name: Install cert-manager and AxonOps operator
  hosts: localhost
  connection: local
  gather_facts: false

  roles:
    - role: axonops.axonops.operator
      vars:
        axonops_operator_install_cert_manager: true
        axonops_operator_cert_manager_version: "v1.20.1"
        axonops_operator_install_operator: true
        axonops_operator_helm_values:
          certManager:
            enable: true
        axonops_operator_platforms: []
```

### Full — cert-manager, operator, and a platform (simple mode)

Installs the full stack and deploys a single `AxonOpsPlatform` CR using the role's template. Suitable for development and single-tenant deployments where the default manifest structure is sufficient.

```yaml
- name: Deploy AxonOps stack
  hosts: localhost
  connection: local
  gather_facts: false

  roles:
    - role: axonops.axonops.operator
      vars:
        axonops_operator_install_cert_manager: true
        axonops_operator_install_operator: true
        axonops_operator_helm_values:
          certManager:
            enable: true
        axonops_operator_platforms:
          - name: axonops
            namespace: axonops
            spec:
              server:
                orgName: "MyOrganization"
              timeSeries: {}
              search: {}
              dashboard: {}
```

### Full — cert-manager, operator, and a platform (custom mode)

Uses `custom_spec` to supply the full manifest for a production-grade platform with resource customisation. Use this when you need fields beyond what the simple template covers, such as replica counts, storage classes, or ingress configuration.

```yaml
- name: Deploy AxonOps stack (production)
  hosts: localhost
  connection: local
  gather_facts: false

  roles:
    - role: axonops.axonops.operator
      vars:
        axonops_operator_install_cert_manager: true
        axonops_operator_install_operator: true
        axonops_operator_wait_timeout: 600
        axonops_operator_helm_values:
          certManager:
            enable: true
          operator:
            watchAllNamespaces: false
            watchNamespaces:
              - axonops-prod
        axonops_operator_platforms:
          - name: axonops-prod
            namespace: axonops-prod
            custom_spec:
              apiVersion: core.axonops.com/v1alpha1
              kind: AxonOpsPlatform
              metadata:
                name: axonops-prod
                namespace: axonops-prod
              spec:
                server:
                  orgName: "ACME Corp"
                  replicas: 3
                  resources:
                    requests:
                      cpu: "2"
                      memory: "4Gi"
                    limits:
                      cpu: "4"
                      memory: "8Gi"
                timeSeries:
                  replicas: 3
                  storage:
                    size: "500Gi"
                    storageClassName: fast-ssd
                search:
                  replicas: 2
                  storage:
                    size: "250Gi"
                    storageClassName: fast-ssd
                dashboard:
                  replicas: 2
                  ingress:
                    enabled: true
                    hosts:
                      - dashboard.axonops.example.com
```

## Tags

Use tags to run only specific sections of the role:

| Tag | Tasks performed |
|-----|----------------|
| `cert-manager` | Install cert-manager via Helm and wait for the webhook to be ready |
| `operator` | Install the `axonops-operator` Helm chart and wait for the controller manager to be ready |
| `platforms` | Deploy `AxonOpsPlatform` CRs for all entries in `axonops_operator_platforms` |

Example — install only cert-manager:

```bash
ansible-playbook site.yml --tags cert-manager
```

Example — skip cert-manager (already installed) and go straight to the operator and platforms:

```bash
ansible-playbook site.yml --skip-tags cert-manager
```

Example — redeploy platform CRs only, without reinstalling the operator:

```bash
ansible-playbook site.yml --tags platforms
```

## Testing

The role has two Molecule scenarios.

### `validate` — no cluster required

Validates variable defaults and template rendering without a Kubernetes cluster. This scenario runs against `localhost` only and does not call any Kubernetes API. It is safe to run in any environment.

```bash
cd roles/operator
molecule converge -s validate
```

The five tests cover:

1. All default variables are set to the expected values
2. `axonops_operator_helm_values` merges correctly with the base CRD values
3. The `AxonOpsPlatform` template renders valid YAML in simple mode with a populated `spec`
4. The template renders valid YAML when `spec` is omitted (minimal entry)
5. The template correctly includes `labels` and `annotations` in the CR metadata

### `default` — full integration test (requires Kind)

Creates a Kind cluster named `molecule-operator`, installs cert-manager and the operator into it, then verifies that:

- The `cert-manager` and `cert-manager-webhook` deployments are ready
- The `axonops-operator-controller-manager` deployment is ready
- The `axonopsplatforms.core.axonops.com` CRD is installed

```bash
# Install Kind first: https://kind.sigs.k8s.io/docs/user/quick-start/
cd roles/operator
molecule test
```

The cleanup stage deletes the Kind cluster after the test run completes. To leave the cluster running for inspection:

```bash
molecule converge
molecule verify
# inspect the cluster
molecule cleanup
```

## Notes

- **cert-manager webhook**: The role waits for `cert-manager-webhook` to be ready before installing the operator. Skipping this wait (by setting `axonops_operator_install_cert_manager: false` when cert-manager is not yet ready) will cause the operator install to fail with webhook certificate errors.
- **CRD retention**: `axonops_operator_crd_keep` defaults to `true`. Setting it to `false` means that uninstalling the Helm release will also delete all `AxonOpsPlatform` CRs in the cluster.
- **Namespace creation**: The role creates namespaces for cert-manager, the operator, and each platform entry if they do not already exist.
- **Idempotency**: The role is idempotent. Running it again will update existing resources if the Helm values or CR spec have changed.

## License

See the main collection LICENSE file.

## Author

AxonOps Limited
