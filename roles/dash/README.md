
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
