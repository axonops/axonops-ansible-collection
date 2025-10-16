<div align="center">
  <a href="https://axonops.com/">
    <img src="https://digitalis-marketplace-assets.s3.us-east-1.amazonaws.com/AxonopsDigitalMaster_AxonopsFullLogoBlue.jpg" alt="AxonOps Logo" width="300">
  </a>

  # AxonOps Ansible Collection: Full Deployment Example

  [![Apache Cassandra](https://img.shields.io/badge/Apache%20Cassandra-5.0.5-1287B1?style=for-the-badge&logo=apache-cassandra)](https://cassandra.apache.org/)
  [![Ansible](https://img.shields.io/badge/Ansible-Automation-EE0000?style=for-the-badge&logo=ansible)](https://www.ansible.com/)
  [![AxonOps](https://img.shields.io/badge/AxonOps-Monitoring-4A90E2?style=for-the-badge)](https://axonops.com/)
</div>

---

## Overview

This project provides a complete, production-grade example of deploying a multi-environment Apache Cassandra cluster monitored by AxonOps, using the [AxonOps Ansible Collection](https://github.com/axonops/axonops-ansible-collection). It is designed for DevOps engineers and SREs who want to automate their Cassandra and AxonOps deployments.

This example demonstrates:
- **Multi-Environment Deployments**: Configuration for `dev`, `stg`, and `prd` environments.
- **Infrastructure as Code**: Using Ansible for configuration management.
- **Automated Workflows**: A `Makefile` to simplify setup, deployment, and maintenance tasks.
- **Configuration Management**: A hierarchical variable system using `group_vars` for environment-specific settings.
- **Secrets Management**: Secure handling of credentials and keys with Ansible Vault.
- **Comprehensive Monitoring**: A powerful, data-driven system for configuring AxonOps alerts, integrations, backups, and service checks.

## Table of Contents

- [Prerequisites](#-prerequisites)
- [Project Structure](#-project-structure)
- [Quick Start](#-quick-start)
- [Step-by-Step Deployment Guide](#-step-by-step-deployment-guide)
  - [Step 1: Initial Setup](#step-1-initial-setup)
  - [Step 2: Environment Configuration](#step-2-environment-configuration)
  - [Step 3: Deployment with Makefile](#step-3-deployment-with-makefile)
- [Configuring AxonOps Alerts, Backups, and More](#-configuring-axonops-alerts-backups-and-more)
  - [The `alerts.yml` Playbook](#the-alertsyml-playbook)
  - [Configuration Structure (`alerts-config`)](#configuration-structure-alerts-config)
  - [Applying Configurations](#applying-configurations)
- [Advanced Workflows](#-advanced-workflows)
  - [Applying Configuration-Only Changes](#applying-configuration-only-changes)
  - [Performing a Rolling Restart](#performing-a-rolling-restart)
- [SSL/TLS Configuration](#-ssltls-configuration)
- [Production Go-Live Checklist](#-production-go-live-checklist)
- [Troubleshooting](#-troubleshooting)

## 📋 Prerequisites

Before you begin, ensure you have the following:
1.  **Ansible**: Version 2.9 or later.
2.  **Pipenv**: For managing Python dependencies in an isolated environment.
3.  **SSH Access**: SSH connectivity to all target hosts with a user that has `sudo` privileges.
4.  **Ansible Vault Password**: A file containing the vault password. The default location is `~/.ansible_vault_pass`.
5.  **AxonOps Account**: An AxonOps organization name and agent key.

## 📁 Project Structure

The project is organized to support multiple environments with a clear separation of concerns.

```text
.
├── Makefile                # Main entry point for all operations
├── Pipfile                 # Python dependencies for Pipenv
├── ansible.cfg             # Ansible configuration settings
├── requirements.yml        # Ansible Galaxy collection dependencies
├── inventories/            # Environment-specific host definitions
│   ├── dev-001/hosts.ini
│   ├── stg-01/hosts.ini
│   └── prd-01/hosts.ini
├── group_vars/             # Ansible variable definitions
│   ├── all/                # Global variables for all environments
│   ├── dev-001/            # Overrides for the 'dev-001' environment
│   ├── stg-01/             # Overrides for the 'stg-01' environment
│   └── prd-01/             # Overrides for the 'prd-01' environment
├── files/                  # Static files, such as SSL certificates
│   ├── dev-001/ssl/
│   ├── stg-01/ssl/
│   └── prd-01/ssl/
├── alerts-config/          # Data-driven configuration for AxonOps
│   └── example/            # AxonOps organization name ('example' in this case)
│       ├── alert_endpoints.yml
│       ├── log_alert_rules.yml
│       ├── metric_alert_rules.yml
│       └── dev-001/        # Cluster-specific overrides ('dev-001' cluster)
│           └── alert_routes.yml
└── *.yml                   # Main Ansible playbooks
```

## 🚀 Quick Start

This example is pre-configured for a `dev-01` environment. To deploy it:

1.  **Install Dependencies**:
    ```bash
    make prep
    ```

2.  **Set Environment Variables**:
    Create a vault password file and export the path.
    ```bash
    echo "your-vault-password" > ~/.ansible_vault_pass
    export ANSIBLE_VAULT_PASSWORD_FILE=~/.ansible_vault_pass
    ```

3.  **Deploy**:
    The `Makefile` defaults to the `dev-01` environment and the `root` user. You 
    ```bash
    export ENVIRONMENT=dev-01 # change environment if you need
    export INVENTORY=inventories/${ENVIRONMENT}/hosts.ini

    # Apply OS hardening and common settings
    make common

    # Deploy Cassandra and the AxonOps agent
    make cassandra

    # Get the token from https://console.axonops.cloud/
    export AXONOPS_TOKEN=yDATnYwCxxxx
    # Configure AxonOps alerts, integrations, etc.
    make alerts
    ```

## 📋 Step-by-Step Deployment Guide

### Step 1: Initial Setup

First, prepare your local environment by installing the necessary Ansible collections and Python packages.

1.  **Clone the Repository**:
    ```bash
    git clone <repository_url>
    cd examples/full-example
    ```

2.  **Install Dependencies**:
    The `prep` command uses `pipenv` to create a virtual environment and installs Ansible collections defined in `requirements.yml`.
    ```bash
    make prep
    ```
    Using `pipenv` ensures a consistent and isolated environment, avoiding conflicts with system-wide packages.

### Step 2: Environment Configuration

This example uses a hierarchical configuration model that is easy to adapt to your own infrastructure.

#### 2.1 Inventory (`inventories/`)

The `inventories/` directory contains an INI file for each environment. These files define the hosts that belong to each environment and assign them to Ansible groups.

**Example: `inventories/stg-01/hosts.ini`**
```ini
[stg-01]
10.1.16.6 ansible_hostname=cassandra-01 cassandra_rack=rack1
10.1.16.7 ansible_hostname=cassandra-02 cassandra_rack=rack2
10.1.16.8 ansible_hostname=cassandra-03 cassandra_rack=rack3

[cassandra:children]
stg-01
```
To adapt this, create or modify the `hosts.ini` file for your target environment and list your server IP addresses.

#### 2.2 Variables (`group_vars/`)

Variables are defined in `group_vars/`. This directory contains a subdirectory for each environment and a global `all/` directory.

-   `group_vars/all/`: Contains base configurations that apply to **all** environments (e.g., Cassandra version, default snitch).
-   `group_vars/<environment_name>/`: Contains variables that **override** the global settings for a specific environment.

**⚠️ CRITICAL: You MUST configure group_vars for each environment**

The `group_vars` directory is where you define all environment-specific settings. **This is not optional** - each environment requires its own configuration to work correctly.

**Example Workflow**:
1.  Review the default settings in [group_vars/all/cassandra.yml](group_vars/all/cassandra.yml) and [group_vars/all/axonops.yml](group_vars/all/axonops.yml).
2.  Open the directory for your target environment, e.g., [group_vars/stg-01/](group_vars/stg-01/).
3.  In [cassandra.yml](group_vars/stg-01/cassandra.yml), update `cassandra_cluster_name` and `cassandra_seeds` to match your inventory.
4.  In [axonops.yml](group_vars/stg-01/axonops.yml), update `axon_agent_customer_name` and `axon_agent_key` with your AxonOps credentials (these are pulled from a vault file).
5.  Review and adjust performance settings like heap sizes, compaction throughput, and concurrent operations based on your hardware.

**Key configuration files per environment:**
- **cassandra.yml**: Cassandra-specific settings (seeds, cluster name, performance tuning)
- **axonops.yml**: AxonOps agent configuration (organization name, agent key)
- **ssl.yml**: SSL/TLS configuration for client and internode encryption
- **vault.yml**: Encrypted secrets (passwords, API keys)
- **ssl_vault.yml**: Encrypted SSL certificate passwords

#### 2.3 Secrets Management (Ansible Vault)

Sensitive data like passwords, API keys, and SSL credentials are encrypted using Ansible Vault.

-   Vault files are located in each environment's `group_vars` directory (e.g., [group_vars/stg-01/vault.yml](group_vars/stg-01/vault.yml)).
-   The `Makefile` expects the vault password to be in a file. You can specify its location with the `ANSIBLE_VAULT_PASSWORD_FILE` environment variable.

To edit an encrypted file:
```bash
export ANSIBLE_VAULT_PASSWORD_FILE=~/.ansible_vault_pass
ansible-vault edit group_vars/stg-01/vault.yml
```

### Step 3: Deployment with Makefile

The `Makefile` orchestrates the entire deployment process. The key variables to control its behavior are:

-   `ENVIRONMENT`: The target environment (default: `dev-001`). Must match a directory in `inventories/` and `group_vars/`.
-   `ANSIBLE_USER`: The SSH user for connecting to hosts (default: `root`).
-   `EXTRA`: Additional arguments to pass to `ansible-playbook` (e.g., `--check`, `-vvv`).

**⚠️ Understanding the Makefile is Essential**

The [Makefile](Makefile) is your primary interface for all deployment operations. It provides simple commands that execute complex Ansible playbooks with proper configuration. **You should familiarize yourself with the Makefile before deploying.**

**Common Deployment Commands**:

```bash
# Deploy to the 'stg-01' environment
make cassandra ENVIRONMENT=stg-01

# Deploy to production as the 'ubuntu' user
make cassandra ENVIRONMENT=prd-01 ANSIBLE_USER=ubuntu

# Run a dry-run against staging to see what would change
make cassandra ENVIRONMENT=stg-01 EXTRA="--check --diff"
```

**Main Makefile Targets:**
-   `make prep`: Installs Ansible collections and Python dependencies
-   `make common`: Applies OS hardening and base system configuration
-   `make cassandra`: Deploys Java, Apache Cassandra, and the AxonOps agent
-   `make alerts`: Configures alerts, dashboards, backups, and integrations in AxonOps
-   `make rolling-restart`: Performs a safe, zero-downtime restart of the Cassandra cluster

**Makefile Environment Variables:**

```bash
ENVIRONMENT=stg-01                               # Target environment
ANSIBLE_USER=root                              # SSH user
ANSIBLE_VAULT_PASSWORD_FILE=~/.ansible_vault_pass # Vault password file
PIPENV=true                                      # Use pipenv (default: true)
EXTRA="--check --diff"                           # Extra ansible-playbook arguments
```

## 🔧 Configuring AxonOps Alerts, Backups, and More

This example includes a powerful, data-driven system for managing your AxonOps configuration as code.

### The `alerts.yml` Playbook

The `make alerts` command executes the [alerts.yml](alerts.yml) playbook. This playbook does the following:
1.  Identifies your AxonOps organization and cluster name from Ansible variables.
2.  Loads all `.yml` configuration files from `alerts-config/<org_name>/`.
3.  Loads and merges all `.yml` configuration files from `alerts-config/<org_name>/<cluster_name>/`, allowing cluster-specific overrides.
4.  Passes these configurations as variables to the `axonops.axonops.alerts` role, which communicates with the AxonOps API to apply the settings.

> [!IMPORTANT]  
> Before you can use this playbook, you will need to create the directories `alerts-config/<org_name>/` and `alerts-config/<org_name>/<cluster_name>/` using the examples provided **

### Configuration Structure (`alerts-config`)

All AxonOps configurations are stored in [alerts-config/](alerts-config/). The structure is hierarchical:

-   **Organization Level**: `alerts-config/<org_name>/`
    -   Files here define defaults for all clusters within the organization.
-   **Cluster Level**: `alerts-config/<org_name>/<cluster_name>/`
    -   Files here override or extend the organization-level settings for a specific cluster.

**Example Structure:**
```
alerts-config/
└── example-org/
    ├── alert_endpoints.yml       # Organization-wide integrations
    ├── log_alert_rules.yml       # Default log alerts
    ├── metric_alert_rules.yml    # Default metric alerts
    ├── service_checks.yml        # Default service checks
    ├── dev-001/                  # dev-001 cluster overrides
    │   ├── alert_routes.yml
    │   ├── backups.yml
    │   └── service_checks.yml
    ├── stg-01/                   # stg-01 cluster overrides
    │   ├── alert_routes.yml
    │   ├── backups.yml
    │   └── metric_alert_rules.yml
    └── prd-01/                   # prd-01 cluster overrides
        ├── alert_endpoints.yml
        ├── alert_routes.yml
        ├── backups.yml
        └── vault.yml
```

### Configuration Files

-   **`alert_endpoints.yml`**: Define your integration endpoints.
    ```yaml
    # alerts-config/example-org/alert_endpoints.yml
    axonops_slack_integration:
      - name: example_org_slack_integration
        webhook_url: "https://hooks.slack.com/services/..."
    axonops_pagerduty_integration:
      - name: example_org_pagerduty_integration
        integration_key: "..."
    ```

-   **`alert_routes.yml`**: Route alerts to different endpoints based on severity and type.
    ```yaml
    # alerts-config/example-org/prd-01/alert_routes.yml
    axonops_alert_routes:
      - integration_name: example_org_pagerduty_integration
        integration_type: pagerduty
        type: global
        severity: error
      - integration_name: example_org_slack_integration
        integration_type: slack
        type: global
        severity: info/warning
    ```

-   **`metric_alert_rules.yml`** and **`log_alert_rules.yml`**: Define the conditions that trigger alerts. A comprehensive set of rules is provided as a starting point covering CPU, memory, disk, Cassandra latencies, GC pauses, and more.

-   **`service_checks.yml`**: Configure custom health checks using shell scripts or TCP probes (e.g., check_ssl_expiry.sh, check_schema_agreement.sh).

-   **`backups.yml`**: Define backup schedules, destinations (S3, Azure, SFTP, local), and retention policies.

### Applying Configurations

Simply run the `make alerts` command after modifying any files in `alerts-config/`. The playbook is idempotent and will only apply changes.

```bash
# Apply alert configurations for the stg-01 cluster
make alerts ENVIRONMENT=stg-01
```

## ⚙️ Advanced Workflows

### Applying Configuration-Only Changes

To update Cassandra configuration files (`cassandra.yaml`, etc.) without reinstalling or immediately restarting the service, use the `config` tag. This is ideal for tuning production systems.

1.  **Apply Configuration**:
    ```bash
    make cassandra ENVIRONMENT=stg-01 EXTRA="--tags config"
    ```

2.  **Perform a Rolling Restart**:
    The changes will not take effect until the Cassandra service is restarted. Use the rolling restart playbook to do this without downtime.
    ```bash
    make rolling-restart ENVIRONMENT=stg-01
    ```
    Alternatively, you can use the rolling restart feature in the AxonOps UI, which is the recommended method for production environments.

### Performing a Rolling Restart

The [rolling-restart.yml](rolling-restart.yml) playbook provides a safe way to restart the cluster. For each node, it:
1.  Verifies the node is healthy (`UN` status).
2.  Drains the node (`nodetool drain`).
3.  Stops and starts the Cassandra service.
4.  Waits for the node to rejoin the cluster and become healthy again before proceeding to the next one.

To trigger it, run:
```bash
make rolling-restart ENVIRONMENT=prd-01
```

## 🔐 SSL/TLS Configuration

SSL/TLS for both client-to-node and node-to-node encryption is configured via [group_vars/\<env\>/ssl.yml](group_vars/stg-01/ssl.yml).

-   **Certificate Files**: Keystores and truststores are placed in `files/<env>/ssl/`. The `cassandra_ssl_files` variable in `ssl.yml` tells Ansible which files to copy to the nodes.
-   **Automatic Certificate Generation**: For quick setup or development, you can set `cassandra_ssl_create: true` in your `group_vars`. If set, the [_keystore.yml](_keystore.yml) playbook will automatically generate self-signed certificates and keystores for your cluster. **This is not recommended for production.**

## 🚀 Production Go-Live Checklist

Before deploying to the `prd-01` environment, ensure the following steps are complete:

-   [ ] **Replace Self-Signed Certificates**: The default self-signed SSL certificates in `files/prd-01/ssl/` have been replaced with official certificates signed by a trusted Certificate Authority.
-   [ ] **Update Vault with Certificate Passwords**: The [group_vars/prd-01/ssl_vault.yml](group_vars/prd-01/ssl_vault.yml) file has been updated with the passwords for the new production certificates.
-   [ ] **Configure Production Alert Routing**: [alerts-config/example-org/prd-01/alert_routes.yml](alerts-config/example-org/prd-01/alert_routes.yml) is configured to route critical alerts to an incident management system like PagerDuty.
-   [ ] **Review Production Variables**: All variables in [group_vars/prd-01/](group_vars/prd-01/) have been reviewed and confirmed for production use (e.g., heap sizes, compaction throughput).
-   [ ] **Perform a Dry Run**: A `--check` and `--diff` run has been performed against the production environment to validate all intended changes.
    ```bash
    make cassandra ENVIRONMENT=prd-01 EXTRA='--check --diff'
    ```
-   [ ] **Confirm Backup Configuration**: The backup strategy in [alerts-config/example-org/prd-01/backups.yml](alerts-config/example-org/prd-01/backups.yml) has been configured and tested.

## 🔍 Troubleshooting

Use Ansible's ad-hoc command capabilities to quickly check the status of your cluster:

```bash
# Check connectivity to all hosts in the staging environment
pipenv run ansible -i inventories/stg-01/hosts.ini all -m ping

# Check the status of the Cassandra cluster
pipenv run ansible -i inventories/stg-01/hosts.ini cassandra -m shell -a "nodetool status"

# Check the status of the AxonOps agent on all Cassandra nodes
pipenv run ansible -i inventories/stg-01/hosts.ini cassandra -m shell -a "systemctl status axon-agent"

# Tail the Cassandra system log on all nodes
pipenv run ansible -i inventories/stg-01/hosts.ini cassandra -m shell -a "tail -n 100 /var/log/cassandra/system.log"
```
