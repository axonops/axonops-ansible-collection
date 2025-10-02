# AxonOps Dashboard Role

## Overview

The `dash` role installs and configures the AxonOps Dashboard (axon-dash), which provides the web-based user interface for monitoring and managing your Cassandra clusters through AxonOps.

## Requirements

- Ansible 2.9 or higher
- Target system running a supported Linux distribution (RHEL, CentOS, Ubuntu, Debian)
- AxonOps Server installed and accessible
- Network connectivity between the dashboard and AxonOps Server

## Role Variables

### Basic Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `axon_dash_state` | `present` | State of the dashboard: `present` or `absent` |
| `axon_dash_start_at_boot` | `true` | Enable the dashboard to start at boot |
| `axon_dash_version` | `""` (latest) | Specific version to install, or empty for latest |

### Network Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `axon_dash_listen_address` | `127.0.0.1` | IP address the dashboard listens on |
| `axon_dash_listen_port` | `3000` | Port the dashboard listens on |
| `axon_dash_server_endpoint` | `http://127.0.0.1:8080` | URL of the AxonOps Server |

### Nginx Reverse Proxy Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `axon_dash_nginx.enabled` | `false` | Enable Nginx reverse proxy configuration |
| `axon_dash_nginx.hostname` | `{{ ansible_fqdn }}` | Hostname for the Nginx server |
| `axon_dash_nginx.listen` | `{{ ansible_default_ipv4.address }}:443` | Address and port for Nginx to listen on |
| `axon_dash_nginx.ssl_cert` | `/etc/nginx/axon_dash.crt` | Path to SSL certificate |
| `axon_dash_nginx.ssl_key` | `/etc/nginx/axon_dash.key` | Path to SSL private key |
| `axon_dash_nginx.ssl_csr` | `/etc/nginx/axon_dash.csr` | Path to SSL certificate signing request |
| `axon_dash_nginx.ssl_create` | `true` | Automatically create self-signed certificates |
| `axon_dash_nginx.upstream` | `http://localhost:3000` | Upstream backend URL |

### Repository Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `axon_agent_public_repository` | `present` | Enable public repository |
| `axon_agent_beta_repository` | `absent` | Enable beta repository |
| `has_internet_access` | `true` | Whether the system has internet access |

## Dependencies

- AxonOps Server must be installed and running
- (Optional) Nginx if using reverse proxy configuration

## Example Playbooks

### Basic Dashboard Installation (Same Host as Server)

```yaml
- name: Install AxonOps Dashboard
  hosts: axon-server
  become: true

  roles:
    - role: axonops.axonops.dash
```

### Dashboard with Custom Listen Address

```yaml
- name: Install Dashboard Listening on All Interfaces
  hosts: axon-server
  become: true
  vars:
    axon_dash_listen_address: 0.0.0.0
    axon_dash_listen_port: 3000

  roles:
    - role: axonops.axonops.dash
```

### Dashboard with Custom Server Endpoint

```yaml
- name: Install Dashboard with Remote Server
  hosts: dashboard-server
  become: true
  vars:
    axon_dash_server_endpoint: http://axon-server.example.com:8080
    axon_dash_listen_address: 127.0.0.1
    axon_dash_listen_port: 3000

  roles:
    - role: axonops.axonops.dash
```

### Dashboard with Nginx Reverse Proxy

```yaml
- name: Install Dashboard with Nginx SSL Proxy
  hosts: axon-server
  become: true
  vars:
    axon_dash_listen_address: 127.0.0.1
    axon_dash_listen_port: 3000
    axon_dash_nginx:
      enabled: true
      hostname: axonops.example.com
      listen: "{{ ansible_default_ipv4.address }}:443"
      ssl_cert: /etc/nginx/ssl/axonops.crt
      ssl_key: /etc/nginx/ssl/axonops.key
      ssl_create: true
      upstream: http://localhost:3000

  roles:
    - role: axonops.axonops.dash
```

### Complete Server Stack

```yaml
- name: Deploy AxonOps Server and Dashboard
  hosts: axon-server
  become: true
  vars:
    # Server configuration
    axon_server_listen_address: 0.0.0.0
    axon_server_listen_port: 8080

    # Dashboard configuration
    axon_dash_listen_address: 0.0.0.0
    axon_dash_listen_port: 3000
    axon_dash_server_endpoint: http://127.0.0.1:8080

  roles:
    - role: axonops.axonops.elastic
      tags: elastic

    - role: axonops.axonops.cassandra
      tags: cassandra
      when: install_cassandra | default(false)

    - role: axonops.axonops.server
      tags: server

    - role: axonops.axonops.dash
      tags: dash
```

### Dashboard with Specific Version

```yaml
- name: Install Specific Dashboard Version
  hosts: axon-server
  become: true
  vars:
    axon_dash_version: "2.0.4"

  roles:
    - role: axonops.axonops.dash
```

## Recommended Configuration

### Production Setup with Nginx

For production deployments, it's recommended to use a reverse proxy like Nginx in front of the dashboard:

```yaml
- name: Production Dashboard Setup
  hosts: axon-server
  become: true
  vars:
    # Dashboard listens only on localhost
    axon_dash_listen_address: 127.0.0.1
    axon_dash_listen_port: 3000

    # Nginx provides SSL termination
    axon_dash_nginx:
      enabled: true
      hostname: axonops.company.com
      listen: "0.0.0.0:443"
      ssl_cert: /etc/ssl/certs/axonops.crt
      ssl_key: /etc/ssl/private/axonops.key
      ssl_create: false  # Use real certificates
      upstream: http://localhost:3000

  pre_tasks:
    # Install Nginx using your preferred method
    - name: Install Nginx
      ansible.builtin.package:
        name: nginx
        state: present

  roles:
    - role: axonops.axonops.dash
```

## Access the Dashboard

After installation, access the dashboard at:
- Direct access: `http://<server_ip>:3000` (if listening on 0.0.0.0)
- Via Nginx: `https://<hostname>` (if Nginx reverse proxy is configured)

Default credentials are configured during the AxonOps Server setup.

## Tags

- `dash`: Apply all dashboard tasks
- `axonops-dashboard`: Alias for dash tag

## Notes

- **Reverse Proxy**: It's recommended to set up a reverse proxy (like Nginx) in front of the dashboard for production deployments
- **Firewall**: Ensure the dashboard port (default 3000) is accessible from your network if not using a reverse proxy
- **SSL/TLS**: For production, use proper SSL certificates instead of self-signed certificates
- **Same Host**: The dashboard and server are typically installed on the same host, but can be separated if needed
- **Network Access**: Ensure network connectivity between the dashboard and AxonOps Server

## Additional Resources

For Nginx configuration, consider using a community role like:
- [geerlingguy.nginx](https://github.com/geerlingguy/ansible-role-nginx)

## License

See the main collection LICENSE file.

## Author

AxonOps Limited
