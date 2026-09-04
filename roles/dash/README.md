
# AxonOps Dashboard Ansible Role

## Configuration

The configuration is quite simple and requires only a few variables.

### Listen address and port

The dashboard listens on `127.0.0.1:3000` by default. To expose it directly, override `axon_dash_listen_address`. For production deployments, keep the default and place a reverse proxy in front of it.

```yaml
# Override the IP and port that axon-dash should listen on
axon_dash_listen_address: 127.0.0.1
axon_dash_listen_port: 3000
```

### AxonOps server

You will also need to configure the URL of the server. The default configuration assumes both are on the same server.

```yaml
axon_dash_server_endpoint: http://127.0.0.1:8080
```

### Reporting service (Reports v2)

From Reports v2, report generation is handled by a separate `axon-reporting` package that
replaces the deprecated `axon-dash-pdf` / `axon-dash-pdf2` packages. It installs the reporting
service and the dependencies `axon-dash` needs to generate reports, and **must run on the same
host as `axon-dash`** — so this role installs and starts it alongside the dashboard.

Reporting is enabled by default. `axon_dash_reporting_url` (env `AXON_REPORTING_URL`) tells
`axon-dash` where to reach the reporting service and is required for reporting to function; it is
written to `axon-dash.yml` as `axon-dash.reporting_url`. The AxonOps Server also needs to reach
the reporting service — set `axon_server_reports_url` in the `server` role (see its README).

```yaml
axon_dash_reporting_enabled: true                 # install and run axon-reporting (default)
axon_dash_reporting_url: "http://127.0.0.1:8081"  # AXON_REPORTING_URL; required for reporting
axon_reporting_state: present
axon_reporting_version: ""                         # pin a version, e.g. "1.2.3"; empty = latest
axon_reporting_start_at_boot: true
# axon_reporting_download_path: ""                 # offline install: path to the .rpm on the control node
```

Set `axon_dash_reporting_enabled: false` to skip installing the reporting service (for example
when it runs in a separate container, as in AxonOps SaaS). Note that `axon_dash_reporting_url` is
**independent** of `axon_dash_reporting_enabled`: disabling the local install does not blank the
URL, so `axon-dash.yml` still gets `reporting_url` — this is deliberate, letting `axon-dash` point
at a reporting service that runs elsewhere (a remote host or separate container). Set
`axon_dash_reporting_url: ""` to omit `reporting_url` entirely.

> **Variable naming**: dash-integration settings use the `axon_dash_reporting_*` prefix
> (`axon_dash_reporting_enabled`, `axon_dash_reporting_url`); the reporting package's own
> install/runtime settings use the `axon_reporting_*` prefix (`axon_reporting_state`,
> `axon_reporting_version`, `axon_reporting_start_at_boot`, `axon_reporting_download_path`).

> **Upgrading from Reports v1**: this role installs `axon-reporting` alongside any existing
> `axon-dash-pdf` / `axon-dash-pdf2` packages — it does **not** remove them. Once Reports v2 is
> confirmed working, uninstall the old packages manually.

### Built-in nginx proxy (optional)

The role can configure an nginx reverse proxy with TLS in front of the dashboard. Set `axon_dash_nginx.enabled` to `true` to activate it.

```yaml
axon_dash_nginx:
  enabled: true
  hostname: "{{ ansible_fqdn }}"
  listen: "{{ ansible_default_ipv4.address }}:443"
  ssl_cert: "/etc/nginx/axon_dash.crt"
  ssl_key: "/etc/nginx/axon_dash.key"
  ssl_csr: "/etc/nginx/axon_dash.csr"
  ssl_create: true   # generate a self-signed certificate automatically
  upstream: http://localhost:3000
```

## Running

```yaml
- hosts: axon-server
  become: true
  roles:
    - role: axonops.axonops.dash
      tags: axonops-dashboard
      vars:
        axon_dash_listen_address: 127.0.0.1
        axon_dash_server_endpoint: http://127.0.0.1:8080
```
